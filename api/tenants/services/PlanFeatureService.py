"""
Plan Feature Service

This module provides business logic for managing plan features
including feature activation, deactivation, and validation.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.utils import timezone
from ..models.plan import PlanFeature, Plan
from .base import BaseService


class PlanFeatureService(BaseService):
    """
    Service class for managing plan features.
    
    Provides business logic for feature operations including:
    - Feature activation and deactivation
    - Feature validation and compatibility checks
    - Feature usage tracking
    - Feature dependency management
    """
    
    @staticmethod
    def create_feature(plan, feature_data):
        """
        Create a new feature for a plan.
        
        Args:
            plan (Plan): Plan to add feature to
            feature_data (dict): Feature data
            
        Returns:
            PlanFeature: Created feature
            
        Raises:
            ValidationError: If feature data is invalid
        """
        try:
            with transaction.atomic():
                # Validate feature data
                PlanFeatureService._validate_feature_data(feature_data, plan)
                
                # Check for duplicate features
                if PlanFeature.objects.filter(
                    plan=plan,
                    feature_key=feature_data.get('feature_key')
                ).exists():
                    raise ValidationError(_('Feature already exists for this plan'))
                
                # Create feature
                feature = PlanFeature.objects.create(
                    plan=plan,
                    feature_key=feature_data['feature_key'],
                    feature_name=feature_data.get('feature_name', feature_data['feature_key']),
                    feature_type=feature_data.get('feature_type', 'boolean'),
                    value=feature_data.get('value', True),
                    unit=feature_data.get('unit', ''),
                    description=feature_data.get('description', ''),
                    is_active=feature_data.get('is_active', True),
                    is_required=feature_data.get('is_required', False),
                    sort_order=feature_data.get('sort_order', 0),
                    metadata=feature_data.get('metadata', {})
                )
                
                return feature
                
        except Exception as e:
            raise ValidationError(f"Failed to create feature: {str(e)}")
    
    @staticmethod
    def update_feature(feature, feature_data):
        """
        Update an existing feature.
        
        Args:
            feature (PlanFeature): Feature to update
            feature_data (dict): Updated feature data
            
        Returns:
            PlanFeature: Updated feature
            
        Raises:
            ValidationError: If feature data is invalid
        """
        try:
            with transaction.atomic():
                # Validate feature data
                PlanFeatureService._validate_feature_data(feature_data, feature.plan, update=True)
                
                # Update feature fields
                for field, value in feature_data.items():
                    if hasattr(feature, field) and field not in ['id', 'plan', 'created_at']:
                        setattr(feature, field, value)
                
                feature.save()
                return feature
                
        except Exception as e:
            raise ValidationError(f"Failed to update feature: {str(e)}")
    
    @staticmethod
    def activate_feature(feature):
        """
        Activate a feature.
        
        Args:
            feature (PlanFeature): Feature to activate
            
        Returns:
            PlanFeature: Activated feature
        """
        feature.is_active = True
        feature.save()
        return feature
    
    @staticmethod
    def deactivate_feature(feature):
        """
        Deactivate a feature.
        
        Args:
            feature (PlanFeature): Feature to deactivate
            
        Returns:
            PlanFeature: Deactivated feature
        """
        feature.is_active = False
        feature.save()
        return feature
    
    @staticmethod
    def delete_feature(feature):
        """
        Delete a feature.
        
        Args:
            feature (PlanFeature): Feature to delete
        """
        feature.delete()
    
    @staticmethod
    def get_plan_features(plan, active_only=True):
        """
        Get all features for a plan.
        
        Args:
            plan (Plan): Plan to get features for
            active_only (bool): Whether to get only active features
            
        Returns:
            QuerySet: Plan features
        """
        queryset = PlanFeature.objects.filter(plan=plan)
        if active_only:
            queryset = queryset.filter(is_active=True)
        return queryset.order_by('sort_order', 'feature_name')
    
    @staticmethod
    def get_feature_by_key(plan, feature_key):
        """
        Get a feature by its key.
        
        Args:
            plan (Plan): Plan to search in
            feature_key (str): Feature key
            
        Returns:
            PlanFeature or None: Feature if found
        """
        try:
            return PlanFeature.objects.get(plan=plan, feature_key=feature_key)
        except PlanFeature.DoesNotExist:
            return None
    
    @staticmethod
    def check_feature_availability(plan, feature_key):
        """
        Check if a feature is available for a plan.
        
        Args:
            plan (Plan): Plan to check
            feature_key (str): Feature key to check
            
        Returns:
            dict: Feature availability info
        """
        feature = PlanFeatureService.get_feature_by_key(plan, feature_key)
        
        if not feature:
            return {
                'available': False,
                'reason': 'Feature not found',
                'feature': None
            }
        
        if not feature.is_active:
            return {
                'available': False,
                'reason': 'Feature is not active',
                'feature': feature
            }
        
        return {
            'available': True,
            'reason': 'Feature available',
            'feature': feature
        }
    
    @staticmethod
    def validate_feature_usage(plan, feature_key, usage_data=None):
        """
        Validate if a feature can be used based on plan constraints.
        
        Args:
            plan (Plan): Plan to validate against
            feature_key (str): Feature key to validate
            usage_data (dict): Usage data for validation
            
        Returns:
            dict: Validation result
        """
        availability = PlanFeatureService.check_feature_availability(plan, feature_key)
        
        if not availability['available']:
            return {
                'valid': False,
                'reason': availability['reason'],
                'feature': availability['feature']
            }
        
        feature = availability['feature']
        
        # Additional validation based on feature type
        if feature.feature_type == 'boolean':
            return {
                'valid': True,
                'reason': 'Boolean feature available',
                'feature': feature
            }
        
        elif feature.feature_type == 'numeric':
            if usage_data and 'value' in usage_data:
                max_value = feature.value if isinstance(feature.value, (int, float)) else 0
                if usage_data['value'] > max_value:
                    return {
                        'valid': False,
                        'reason': f'Usage value {usage_data["value"]} exceeds limit {max_value}',
                        'feature': feature
                    }
            
            return {
                'valid': True,
                'reason': 'Numeric feature within limits',
                'feature': feature
            }
        
        elif feature.feature_type == 'text':
            return {
                'valid': True,
                'reason': 'Text feature available',
                'feature': feature
            }
        
        return {
            'valid': True,
            'reason': 'Feature available',
            'feature': feature
        }
    
    @staticmethod
    def copy_features_to_plan(source_plan, target_plan, overwrite=False):
        """
        Copy features from one plan to another.
        
        Args:
            source_plan (Plan): Plan to copy features from
            target_plan (Plan): Plan to copy features to
            overwrite (bool): Whether to overwrite existing features
            
        Returns:
            list: Copied features
        """
        copied_features = []
        source_features = PlanFeatureService.get_plan_features(source_plan)
        
        with transaction.atomic():
            for source_feature in source_features:
                # Check if feature already exists in target
                existing_feature = PlanFeatureService.get_feature_by_key(
                    target_plan, source_feature.feature_key
                )
                
                if existing_feature and not overwrite:
                    continue
                
                # Prepare feature data
                feature_data = {
                    'feature_key': source_feature.feature_key,
                    'feature_name': source_feature.feature_name,
                    'feature_type': source_feature.feature_type,
                    'value': source_feature.value,
                    'unit': source_feature.unit,
                    'description': source_feature.description,
                    'is_active': source_feature.is_active,
                    'is_required': source_feature.is_required,
                    'sort_order': source_feature.sort_order,
                    'metadata': source_feature.metadata
                }
                
                if existing_feature:
                    # Update existing feature
                    updated_feature = PlanFeatureService.update_feature(
                        existing_feature, feature_data
                    )
                    copied_features.append(updated_feature)
                else:
                    # Create new feature
                    new_feature = PlanFeatureService.create_feature(
                        target_plan, feature_data
                    )
                    copied_features.append(new_feature)
        
        return copied_features
    
    @staticmethod
    def get_feature_statistics(plan=None):
        """
        Get feature statistics.
        
        Args:
            plan (Plan): Plan to get statistics for (optional)
            
        Returns:
            dict: Feature statistics
        """
        queryset = PlanFeature.objects.all()
        if plan:
            queryset = queryset.filter(plan=plan)
        
        stats = {
            'total_features': queryset.count(),
            'active_features': queryset.filter(is_active=True).count(),
            'inactive_features': queryset.filter(is_active=False).count(),
            'required_features': queryset.filter(is_required=True).count(),
            'features_by_type': {},
            'features_by_plan': {}
        }
        
        # Count by type
        for feature_type in ['boolean', 'numeric', 'text']:
            stats['features_by_type'][feature_type] = queryset.filter(
                feature_type=feature_type
            ).count()
        
        # Count by plan
        if not plan:
            for plan_obj in Plan.objects.all():
                stats['features_by_plan'][plan_obj.name] = queryset.filter(
                    plan=plan_obj
                ).count()
        
        return stats
    
    @staticmethod
    def _validate_feature_data(feature_data, plan, update=False):
        """
        Validate feature data.
        
        Args:
            feature_data (dict): Feature data to validate
            plan (Plan): Plan the feature belongs to
            update (bool): Whether this is an update operation
            
        Raises:
            ValidationError: If validation fails
        """
        required_fields = ['feature_key']
        if not update:
            required_fields.extend(['feature_name'])
        
        for field in required_fields:
            if field not in feature_data:
                raise ValidationError(f"'{field}' is required")
        
        # Validate feature key format
        feature_key = feature_data['feature_key']
        if not isinstance(feature_key, str) or not feature_key.strip():
            raise ValidationError("Feature key must be a non-empty string")
        
        # Validate feature type
        feature_type = feature_data.get('feature_type', 'boolean')
        valid_types = ['boolean', 'numeric', 'text']
        if feature_type not in valid_types:
            raise ValidationError(f"Feature type must be one of: {', '.join(valid_types)}")
        
        # Validate value based on type
        value = feature_data.get('value')
        if feature_type == 'boolean' and not isinstance(value, bool):
            raise ValidationError("Boolean feature value must be True or False")
        elif feature_type == 'numeric' and not isinstance(value, (int, float)):
            raise ValidationError("Numeric feature value must be a number")
        elif feature_type == 'text' and not isinstance(value, str):
            raise ValidationError("Text feature value must be a string")
