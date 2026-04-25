"""
Feature Flag Service

This service handles feature flag operations including
management, targeting, and rollout control for tenants.
"""

import hashlib
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ..models import Tenant
from ..models.analytics import TenantFeatureFlag, TenantNotification
from ..models.security import TenantAuditLog

User = get_user_model()


class FeatureFlagService:
    """
    Service class for feature flag operations.
    
    This service handles feature flag management, targeting,
    rollout control, and A/B testing for tenants.
    """
    
    @staticmethod
    def create_feature_flag(tenant, flag_data, created_by=None):
        """
        Create a feature flag for tenant.
        
        Args:
            tenant (Tenant): Tenant to create flag for
            flag_data (dict): Feature flag data
            created_by (User): User creating the flag
            
        Returns:
            TenantFeatureFlag: Created feature flag
        """
        with transaction.atomic():
            # Validate flag key uniqueness
            flag_key = flag_data.get('flag_key')
            if TenantFeatureFlag.objects.filter(tenant=tenant, flag_key=flag_key).exists():
                raise ValidationError(f'Feature flag with key "{flag_key}" already exists.')
            
            # Create feature flag
            feature_flag = TenantFeatureFlag.objects.create(
                tenant=tenant,
                flag_key=flag_key,
                name=flag_data.get('name'),
                description=flag_data.get('description'),
                flag_type=flag_data.get('flag_type', 'boolean'),
                is_enabled=flag_data.get('is_enabled', False),
                rollout_pct=flag_data.get('rollout_pct', 0),
                variant=flag_data.get('variant'),
                starts_at=flag_data.get('starts_at'),
                expires_at=flag_data.get('expires_at'),
                target_users=flag_data.get('target_users', []),
                target_segments=flag_data.get('target_segments', []),
                conditions=flag_data.get('conditions', {}),
                metadata=flag_data.get('metadata', {}),
                tags=flag_data.get('tags', []),
            )
            
            # Log creation
            if created_by:
                TenantAuditLog.log_action(
                    tenant=tenant,
                    action='config_change',
                    actor=created_by,
                    model_name='TenantFeatureFlag',
                    object_id=str(feature_flag.id),
                    object_repr=str(feature_flag),
                    description=f"Feature flag '{feature_flag.name}' created",
                    metadata={
                        'flag_key': flag_key,
                        'flag_type': feature_flag.flag_type,
                        'is_enabled': feature_flag.is_enabled,
                    }
                )
            
            return feature_flag
    
    @staticmethod
    def update_feature_flag(feature_flag, flag_data, updated_by=None):
        """
        Update a feature flag.
        
        Args:
            feature_flag (TenantFeatureFlag): Feature flag to update
            flag_data (dict): Update data
            updated_by (User): User updating the flag
            
        Returns:
            TenantFeatureFlag: Updated feature flag
        """
        with transaction.atomic():
            # Store old values for audit
            old_values = {
                'is_enabled': feature_flag.is_enabled,
                'rollout_pct': feature_flag.rollout_pct,
                'variant': feature_flag.variant,
            }
            
            # Update fields
            updatable_fields = [
                'name', 'description', 'flag_type', 'is_enabled', 'rollout_pct',
                'variant', 'starts_at', 'expires_at', 'target_users', 'target_segments',
                'conditions', 'metadata', 'tags'
            ]
            
            for field in updatable_fields:
                if field in flag_data:
                    setattr(feature_flag, field, flag_data[field])
            
            feature_flag.save()
            
            # Log update
            if updated_by:
                changes = {}
                for field, old_value in old_values.items():
                    new_value = getattr(feature_flag, field)
                    if old_value != new_value:
                        changes[field] = {'old': old_value, 'new': new_value}
                
                if changes:
                    TenantAuditLog.log_action(
                        tenant=feature_flag.tenant,
                        action='config_change',
                        actor=updated_by,
                        model_name='TenantFeatureFlag',
                        object_id=str(feature_flag.id),
                        object_repr=str(feature_flag),
                        changes=changes,
                        description=f"Feature flag '{feature_flag.name}' updated"
                    )
            
            return feature_flag
    
    @staticmethod
    def enable_feature_flag(feature_flag, enabled_by=None):
        """
        Enable a feature flag.
        
        Args:
            feature_flag (TenantFeatureFlag): Feature flag to enable
            enabled_by (User): User enabling the flag
            
        Returns:
            TenantFeatureFlag: Enabled feature flag
        """
        feature_flag.enable()
        
        # Log enablement
        if enabled_by:
            TenantAuditLog.log_action(
                tenant=feature_flag.tenant,
                action='config_change',
                actor=enabled_by,
                model_name='TenantFeatureFlag',
                object_id=str(feature_flag.id),
                object_repr=str(feature_flag),
                description=f"Feature flag '{feature_flag.name}' enabled"
            )
        
        return feature_flag
    
    @staticmethod
    def disable_feature_flag(feature_flag, disabled_by=None):
        """
        Disable a feature flag.
        
        Args:
            feature_flag (TenantFeatureFlag): Feature flag to disable
            disabled_by (User): User disabling the flag
            
        Returns:
            TenantFeatureFlag: Disabled feature flag
        """
        feature_flag.disable()
        
        # Log disablement
        if disabled_by:
            TenantAuditLog.log_action(
                tenant=feature_flag.tenant,
                action='config_change',
                actor=disabled_by,
                model_name='TenantFeatureFlag',
                object_id=str(feature_flag.id),
                object_repr=str(feature_flag),
                description=f"Feature flag '{feature_flag.name}' disabled"
            )
        
        return feature_flag
    
    @staticmethod
    def rollout_to_percentage(feature_flag, percentage, rolled_out_by=None):
        """
        Rollout feature flag to a specific percentage.
        
        Args:
            feature_flag (TenantFeatureFlag): Feature flag to rollout
            percentage (int): Percentage to rollout to (0-100)
            rolled_out_by (User): User performing rollout
            
        Returns:
            TenantFeatureFlag: Updated feature flag
        """
        feature_flag.rollout_to_percentage(percentage)
        
        # Log rollout
        if rolled_out_by:
            TenantAuditLog.log_action(
                tenant=feature_flag.tenant,
                action='config_change',
                actor=rolled_out_by,
                model_name='TenantFeatureFlag',
                object_id=str(feature_flag.id),
                object_repr=str(feature_flag),
                description=f"Feature flag '{feature_flag.name}' rolled out to {percentage}%",
                metadata={'rollout_percentage': percentage}
            )
        
        return feature_flag
    
    @staticmethod
    def is_feature_enabled(tenant, flag_key, user=None):
        """
        Check if a feature flag is enabled for a user.
        
        Args:
            tenant (Tenant): Tenant to check flag for
            flag_key (str): Feature flag key
            user (User): User to check flag for
            
        Returns:
            bool: Whether feature is enabled
        """
        try:
            feature_flag = TenantFeatureFlag.objects.get(
                tenant=tenant,
                flag_key=flag_key
            )
            return feature_flag.is_enabled_for_user(user)
        except TenantFeatureFlag.DoesNotExist:
            return False
    
    @staticmethod
    def get_variant_for_user(tenant, flag_key, user):
        """
        Get A/B testing variant for user.
        
        Args:
            tenant (Tenant): Tenant to get variant for
            flag_key (str): Feature flag key
            user (User): User to get variant for
            
        Returns:
            str: Variant name or None
        """
        try:
            feature_flag = TenantFeatureFlag.objects.get(
                tenant=tenant,
                flag_key=flag_key
            )
            return feature_flag.get_variant_for_user(user)
        except TenantFeatureFlag.DoesNotExist:
            return None
    
    @staticmethod
    def get_user_feature_flags(tenant, user):
        """
        Get all enabled feature flags for a user.
        
        Args:
            tenant (Tenant): Tenant to get flags for
            user (User): User to get flags for
            
        Returns:
            dict: Enabled feature flags and variants
        """
        flags = TenantFeatureFlag.objects.filter(
            tenant=tenant,
            is_active=True
        )
        
        user_flags = {
            'enabled_flags': [],
            'variants': {},
        }
        
        for flag in flags:
            if flag.is_enabled_for_user(user):
                user_flags['enabled_flags'].append({
                    'key': flag.flag_key,
                    'name': flag.name,
                    'type': flag.flag_type,
                })
                
                # Get variant if applicable
                variant = flag.get_variant_for_user(user)
                if variant:
                    user_flags['variants'][flag.flag_key] = variant
        
        return user_flags
    
    @staticmethod
    def get_feature_flag_analytics(tenant, flag_key=None, days=30):
        """
        Get analytics for feature flags.
        
        Args:
            tenant (Tenant): Tenant to get analytics for
            flag_key (str): Specific flag key (optional)
            days (int): Number of days to analyze
            
        Returns:
            dict: Feature flag analytics
        """
        from django.utils import timezone
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        # Get feature flags
        if flag_key:
            flags = TenantFeatureFlag.objects.filter(
                tenant=tenant,
                flag_key=flag_key
            )
        else:
            flags = TenantFeatureFlag.objects.filter(tenant=tenant)
        
        analytics = {
            'period': {
                'start_date': start_date.date(),
                'end_date': timezone.now().date(),
                'days': days,
            },
            'flags': {},
            'summary': {},
        }
        
        total_flags = flags.count()
        active_flags = flags.filter(is_active=True).count()
        enabled_flags = flags.filter(is_enabled=True).count()
        
        for flag in flags:
            flag_data = {
                'key': flag.flag_key,
                'name': flag.name,
                'type': flag.flag_type,
                'is_enabled': flag.is_enabled,
                'is_active': flag.is_active(),
                'rollout_pct': flag.rollout_pct,
                'variant': flag.variant,
                'target_users_count': len(flag.target_users) if flag.target_users else 0,
                'target_segments_count': len(flag.target_segments) if flag.target_segments else 0,
                'created_at': flag.created_at,
            }
            
            # Calculate usage statistics
            flag_data['usage'] = FeatureFlagService._calculate_flag_usage(flag, start_date)
            
            analytics['flags'][flag.flag_key] = flag_data
        
        # Summary statistics
        analytics['summary'] = {
            'total_flags': total_flags,
            'active_flags': active_flags,
            'enabled_flags': enabled_flags,
            'flags_by_type': FeatureFlagService._get_flags_by_type(flags),
            'flags_by_status': FeatureFlagService._get_flags_by_status(flags),
        }
        
        return analytics
    
    @staticmethod
    def _calculate_flag_usage(flag, start_date):
        """Calculate usage statistics for a feature flag."""
        # This would query your feature flag usage logs
        # For now, return placeholder data
        return {
            'total_evaluations': 0,
            'enabled_evaluations': 0,
            'disabled_evaluations': 0,
            'usage_percentage': 0,
            'unique_users': 0,
        }
    
    @staticmethod
    def _get_flags_by_type(flags):
        """Get flags breakdown by type."""
        from django.db.models import Count
        
        return list(
            flags.values('flag_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
    
    @staticmethod
    def _get_flags_by_status(flags):
        """Get flags breakdown by status."""
        from django.db.models import Count
        
        return list(
            flags.values('is_enabled', 'is_active')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
    
    @staticmethod
    def create_ab_test(tenant, test_data, created_by=None):
        """
        Create an A/B test using feature flags.
        
        Args:
            tenant (Tenant): Tenant to create test for
            test_data (dict): A/B test configuration
            created_by (User): User creating the test
            
        Returns:
            dict: A/B test configuration
        """
        with transaction.atomic():
            test_name = test_data.get('name')
            variants = test_data.get('variants', ['control', 'test'])
            rollout_pct = test_data.get('rollout_pct', 50)
            
            # Create feature flags for each variant
            created_flags = []
            
            for variant in variants:
                flag_data = {
                    'flag_key': f"ab_test_{test_name}_{variant}",
                    'name': f"A/B Test: {test_name} - {variant}",
                    'description': f"A/B test variant: {variant}",
                    'flag_type': 'conditional',
                    'is_enabled': True,
                    'rollout_pct': rollout_pct,
                    'variant': variant,
                    'metadata': {
                        'ab_test': True,
                        'test_name': test_name,
                        'variant': variant,
                    },
                    'tags': ['ab_test', test_name],
                }
                
                flag = FeatureFlagService.create_feature_flag(tenant, flag_data, created_by)
                created_flags.append(flag)
            
            return {
                'success': True,
                'message': f"A/B test '{test_name}' created with {len(variants)} variants",
                'test_name': test_name,
                'variants': variants,
                'flags': [
                    {
                        'flag_key': flag.flag_key,
                        'variant': flag.variant,
                    }
                    for flag in created_flags
                ],
            }
    
    @staticmethod
    def get_ab_test_results(tenant, test_name):
        """
        Get results for an A/B test.
        
        Args:
            tenant (Tenant): Tenant to get results for
            test_name (str): A/B test name
            
        Returns:
            dict: A/B test results
        """
        # Get all feature flags for this test
        flags = TenantFeatureFlag.objects.filter(
            tenant=tenant,
            metadata__ab_test=True,
            metadata__test_name=test_name
        )
        
        if not flags.exists():
            raise ValidationError(f"A/B test '{test_name}' not found.")
        
        results = {
            'test_name': test_name,
            'variants': {},
            'summary': {},
        }
        
        total_users = 0
        variant_data = []
        
        for flag in flags:
            variant = flag.metadata.get('variant')
            
            # Calculate variant statistics
            variant_stats = FeatureFlagService._calculate_variant_stats(flag)
            variant_data.append({
                'variant': variant,
                'flag_key': flag.flag_key,
                'stats': variant_stats,
            })
            
            total_users += variant_stats.get('user_count', 0)
        
        results['variants'] = variant_data
        results['summary'] = {
            'total_users': total_users,
            'total_variants': len(variant_data),
            'test_duration_days': FeatureFlagService._calculate_test_duration(flags),
        }
        
        return results
    
    @staticmethod
    def _calculate_variant_stats(flag):
        """Calculate statistics for a variant."""
        # This would query your A/B test analytics
        # For now, return placeholder data
        return {
            'user_count': 0,
            'conversions': 0,
            'conversion_rate': 0,
            'revenue': 0,
            'avg_session_duration': 0,
        }
    
    @staticmethod
    def _calculate_test_duration(flags):
        """Calculate test duration in days."""
        if not flags.exists():
            return 0
        
        created_at = flags.earliest('created_at').created_at
        duration = (timezone.now() - created_at).days
        return max(0, duration)
    
    @staticmethod
    def cleanup_expired_flags():
        """
        Clean up expired feature flags.
        
        Returns:
            dict: Cleanup results
        """
        expired_flags = TenantFeatureFlag.objects.filter(
            expires_at__lt=timezone.now(),
            is_active=True
        )
        
        results = {
            'total_expired': expired_flags.count(),
            'flags_processed': 0,
            'details': [],
        }
        
        for flag in expired_flags:
            # Disable expired flag
            flag.is_active = False
            flag.save(update_fields=['is_active'])
            
            results['flags_processed'] += 1
            results['details'].append({
                'flag_key': flag.flag_key,
                'name': flag.name,
                'expired_at': flag.expires_at,
            })
            
            # Log cleanup
            TenantAuditLog.log_action(
                tenant=flag.tenant,
                action='config_change',
                model_name='TenantFeatureFlag',
                description=f"Feature flag '{flag.name}' expired and deactivated",
                metadata={
                    'flag_key': flag.flag_key,
                    'expired_at': flag.expires_at.isoformat(),
                }
            )
        
        return results
    
    @staticmethod
    def get_feature_flag_recommendations(tenant):
        """
        Get feature flag recommendations for tenant.
        
        Args:
            tenant (Tenant): Tenant to get recommendations for
            
        Returns:
            list: List of recommendations
        """
        recommendations = []
        
        # Check for flags that should be cleaned up
        expired_flags = TenantFeatureFlag.objects.filter(
            tenant=tenant,
            expires_at__lt=timezone.now(),
            is_active=True
        )
        
        if expired_flags.exists():
            recommendations.append({
                'type': 'cleanup',
                'priority': 'medium',
                'title': 'Clean Up Expired Flags',
                'description': f"You have {expired_flags.count()} expired feature flags that should be cleaned up.",
                'action': 'Clean Up Flags',
                'count': expired_flags.count(),
            })
        
        # Check for flags with low usage
        all_flags = TenantFeatureFlag.objects.filter(tenant=tenant, is_active=True)
        
        for flag in all_flags:
            usage = FeatureFlagService._calculate_flag_usage(flag, timezone.now() - timedelta(days=30))
            
            if usage['usage_percentage'] < 5:  # Less than 5% usage
                recommendations.append({
                    'type': 'optimization',
                    'priority': 'low',
                    'title': 'Low Usage Flag',
                    'description': f"Feature flag '{flag.name}' has low usage ({usage['usage_percentage']:.1f}%).",
                    'action': 'Review Flag',
                    'flag_key': flag.flag_key,
                    'usage_percentage': usage['usage_percentage'],
                })
        
        # Check for flags that could be fully rolled out
        rollout_flags = all_flags.filter(
            flag_type='percentage',
            rollout_pct__gte=90  # 90% or more rollout
        )
        
        for flag in rollout_flags:
            recommendations.append({
                'type': 'optimization',
                'priority': 'low',
                'title': 'Consider Full Rollout',
                'description': f"Feature flag '{flag.name}' is rolled out to {flag.rollout_pct}% and could be fully enabled.",
                'action': 'Enable Flag',
                'flag_key': flag.flag_key,
                'rollout_pct': flag.rollout_pct,
            })
        
        return recommendations
