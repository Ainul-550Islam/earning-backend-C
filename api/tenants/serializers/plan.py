"""
Plan Serializers

This module contains serializers for plan-related models including
Plan, PlanFeature, PlanUpgrade, PlanUsage, and PlanQuota.
"""

from rest_framework import serializers
from django.utils import timezone
from ..models.plan import Plan, PlanFeature, PlanUpgrade, PlanUsage, PlanQuota


class PlanSerializer(serializers.ModelSerializer):
    """
    Serializer for Plan model with comprehensive field mapping.
    """
    yearly_discount_percentage = serializers.SerializerMethodField()
    has_trial = serializers.SerializerMethodField()
    can_downgrade_to_plans = serializers.SerializerMethodField()
    features_count = serializers.SerializerMethodField()
    quotas_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Plan
        fields = [
            'id', 'name', 'slug', 'description', 'plan_type', 'billing_cycle',
            'price_monthly', 'price_yearly', 'setup_fee', 'max_users',
            'max_publishers', 'max_smartlinks', 'max_campaigns',
            'api_calls_per_day', 'api_calls_per_hour', 'storage_gb',
            'bandwidth_gb_per_month', 'features', 'feature_flags',
            'is_active', 'is_public', 'is_upgrade_only', 'sort_order',
            'is_featured', 'badge_text', 'trial_days', 'trial_requires_payment',
            'can_downgrade', 'can_upgrade', 'downgrade_to_plans',
            'yearly_discount_percentage', 'has_trial', 'features_count',
            'quotas_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_yearly_discount_percentage(self, obj):
        """Calculate yearly discount percentage."""
        return obj.yearly_discount_percentage
    
    def get_has_trial(self, obj):
        """Check if plan offers trial."""
        return obj.has_trial
    
    def get_can_downgrade_to_plans(self, obj):
        """Get plans that can be downgraded to."""
        return [
            {
                'id': str(plan.id),
                'name': plan.name,
                'slug': plan.slug,
                'plan_type': plan.plan_type,
                'price_monthly': float(plan.price_monthly),
            }
            for plan in obj.downgrade_to_plans.all()
        ]
    
    def get_features_count(self, obj):
        """Get count of features."""
        return len(obj.features) if obj.features else 0
    
    def get_quotas_count(self, obj):
        """Get count of quotas."""
        return obj.quotas.count()
    
    def validate(self, attrs):
        """Validate plan data."""
        # Validate pricing
        for field in ['price_monthly', 'price_yearly', 'setup_fee']:
            if field in attrs:
                price = attrs[field]
                if price < 0:
                    raise serializers.ValidationError(f"{field} cannot be negative.")
        
        # Validate limits
        limit_fields = [
            'max_users', 'max_publishers', 'max_smartlinks', 'max_campaigns',
            'api_calls_per_day', 'api_calls_per_hour', 'storage_gb',
            'bandwidth_gb_per_month', 'trial_days'
        ]
        
        for field in limit_fields:
            if field in attrs:
                limit = attrs[field]
                if limit < 0:
                    raise serializers.ValidationError(f"{field} cannot be negative.")
        
        # Validate trial days
        if 'trial_days' in attrs and attrs['trial_days'] > 365:
            raise serializers.ValidationError("Trial days cannot exceed 365.")
        
        return attrs


class PlanCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new plans.
    """
    quotas = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        write_only=True
    )
    
    class Meta:
        model = Plan
        fields = [
            'name', 'slug', 'description', 'plan_type', 'billing_cycle',
            'price_monthly', 'price_yearly', 'setup_fee', 'max_users',
            'max_publishers', 'max_smartlinks', 'max_campaigns',
            'api_calls_per_day', 'api_calls_per_hour', 'storage_gb',
            'bandwidth_gb_per_month', 'features', 'feature_flags',
            'is_active', 'is_public', 'is_upgrade_only', 'sort_order',
            'is_featured', 'badge_text', 'trial_days', 'trial_requires_payment',
            'can_downgrade', 'can_upgrade', 'quotas'
        ]
    
    def validate_slug(self, value):
        """Validate slug uniqueness."""
        if Plan.objects.filter(slug=value).exists():
            raise serializers.ValidationError("Plan slug already exists.")
        return value
    
    def create(self, validated_data):
        """Create plan with quotas."""
        quotas_data = validated_data.pop('quotas', [])
        plan = Plan.objects.create(**validated_data)
        
        # Create quotas
        for quota_data in quotas_data:
            PlanQuota.objects.create(plan=plan, **quota_data)
        
        return plan


class PlanUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating existing plans.
    """
    quotas = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        write_only=True
    )
    
    class Meta:
        model = Plan
        fields = [
            'name', 'description', 'plan_type', 'billing_cycle',
            'price_monthly', 'price_yearly', 'setup_fee', 'max_users',
            'max_publishers', 'max_smartlinks', 'max_campaigns',
            'api_calls_per_day', 'api_calls_per_hour', 'storage_gb',
            'bandwidth_gb_per_month', 'features', 'feature_flags',
            'is_active', 'is_public', 'is_upgrade_only', 'sort_order',
            'is_featured', 'badge_text', 'trial_days', 'trial_requires_payment',
            'can_downgrade', 'can_upgrade', 'quotas'
        ]
    
    def update(self, instance, validated_data):
        """Update plan with quotas."""
        quotas_data = validated_data.pop('quotas', None)
        
        # Update plan fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update quotas if provided
        if quotas_data is not None:
            # Remove existing quotas
            instance.quotas.all().delete()
            
            # Create new quotas
            for quota_data in quotas_data:
                PlanQuota.objects.create(plan=instance, **quota_data)
        
        return instance


class PlanFeatureSerializer(serializers.ModelSerializer):
    """
    Serializer for PlanFeature model.
    """
    class Meta:
        model = PlanFeature
        fields = [
            'id', 'name', 'key', 'description', 'feature_type', 'default_value',
            'min_value', 'max_value', 'allowed_values', 'display_name', 'icon',
            'category', 'sort_order', 'is_active', 'is_public', 'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, attrs):
        """Validate feature data."""
        # Validate enum type
        feature_type = attrs.get('feature_type')
        if feature_type == 'enum':
            allowed_values = attrs.get('allowed_values', [])
            if not allowed_values:
                raise serializers.ValidationError("Enum type must have allowed values defined.")
        
        # Validate min/max values
        min_value = attrs.get('min_value')
        max_value = attrs.get('max_value')
        
        if min_value is not None and max_value is not None:
            if min_value > max_value:
                raise serializers.ValidationError("Min value cannot be greater than max value.")
        
        return attrs


class PlanUpgradeSerializer(serializers.ModelSerializer):
    """
    Serializer for PlanUpgrade model.
    """
    from_plan_details = serializers.SerializerMethodField()
    to_plan_details = serializers.SerializerMethodField()
    processed_by_details = serializers.SerializerMethodField()
    
    class Meta:
        model = PlanUpgrade
        fields = [
            'id', 'tenant', 'from_plan', 'to_plan', 'from_plan_details',
            'to_plan_details', 'upgraded_at', 'effective_from', 'old_price',
            'new_price', 'price_difference', 'reason', 'notes',
            'processed_by', 'processed_by_details', 'is_automatic',
            'payment_method', 'transaction_id', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'upgraded_at', 'created_at', 'updated_at'
        ]
    
    def get_from_plan_details(self, obj):
        """Get from plan details."""
        if obj.from_plan:
            return {
                'id': str(obj.from_plan.id),
                'name': obj.from_plan.name,
                'slug': obj.from_plan.slug,
                'plan_type': obj.from_plan.plan_type,
            }
        return None
    
    def get_to_plan_details(self, obj):
        """Get to plan details."""
        if obj.to_plan:
            return {
                'id': str(obj.to_plan.id),
                'name': obj.to_plan.name,
                'slug': obj.to_plan.slug,
                'plan_type': obj.to_plan.plan_type,
            }
        return None
    
    def get_processed_by_details(self, obj):
        """Get processed by user details."""
        if obj.processed_by:
            return {
                'id': str(obj.processed_by.id),
                'username': obj.processed_by.username,
                'email': obj.processed_by.email,
            }
        return None
    
    def validate(self, attrs):
        """Validate upgrade data."""
        from_plan = attrs.get('from_plan')
        to_plan = attrs.get('to_plan')
        
        if from_plan == to_plan:
            raise serializers.ValidationError("From plan and to plan cannot be the same.")
        
        return attrs


class PlanUsageSerializer(serializers.ModelSerializer):
    """
    Serializer for PlanUsage model.
    """
    tenant_details = serializers.SerializerMethodField()
    period_display = serializers.SerializerMethodField()
    api_calls_percentage = serializers.SerializerMethodField()
    storage_percentage = serializers.SerializerMethodField()
    users_percentage = serializers.SerializerMethodField()
    over_limit_metrics = serializers.SerializerMethodField()
    
    class Meta:
        model = PlanUsage
        fields = [
            'id', 'tenant', 'tenant_details', 'period', 'period_display',
            'period_start', 'period_end', 'api_calls_used', 'storage_used_gb',
            'bandwidth_used_gb', 'users_used', 'publishers_used',
            'smartlinks_used', 'campaigns_used', 'additional_metrics',
            'api_calls_limit', 'storage_limit_gb', 'bandwidth_limit_gb',
            'users_limit', 'publishers_limit', 'smartlinks_limit',
            'campaigns_limit', 'api_calls_percentage', 'storage_percentage',
            'users_percentage', 'over_limit_metrics', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']
    
    def get_tenant_details(self, obj):
        """Get tenant details."""
        return {
            'id': str(obj.tenant.id),
            'name': obj.tenant.name,
            'slug': obj.tenant.slug,
        }
    
    def get_period_display(self, obj):
        """Get period display name."""
        return obj.get_period_display()
    
    def get_api_calls_percentage(self, obj):
        """Calculate API calls usage percentage."""
        return obj.api_calls_percentage
    
    def get_storage_percentage(self, obj):
        """Calculate storage usage percentage."""
        return obj.storage_percentage
    
    def get_users_percentage(self, obj):
        """Calculate users usage percentage."""
        return obj.users_percentage
    
    def get_over_limit_metrics(self, obj):
        """Get metrics that are over limit."""
        over_limit = []
        
        metrics = [
            ('api_calls', obj.api_calls_used, obj.api_calls_limit),
            ('storage', obj.storage_used_gb, obj.storage_limit_gb),
            ('users', obj.users_used, obj.users_limit),
            ('publishers', obj.publishers_used, obj.publishers_limit),
            ('smartlinks', obj.smartlinks_used, obj.smartlinks_limit),
            ('campaigns', obj.campaigns_used, obj.campaigns_limit),
        ]
        
        for metric_name, used, limit in metrics:
            if limit > 0 and used > limit:
                over_limit.append({
                    'metric': metric_name,
                    'used': used,
                    'limit': limit,
                    'overage': used - limit,
                })
        
        return over_limit


class PlanQuotaSerializer(serializers.ModelSerializer):
    """
    Serializer for PlanQuota model.
    """
    plan_details = serializers.SerializerMethodField()
    is_over_limit_example = serializers.SerializerMethodField()
    
    class Meta:
        model = PlanQuota
        fields = [
            'id', 'plan', 'plan_details', 'feature_key', 'hard_limit', 'soft_limit',
            'warning_threshold', 'quota_type', 'overage_allowed',
            'overage_price_per_unit', 'reset_period', 'reset_day_of_month',
            'display_name', 'unit', 'is_over_limit_example', 'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'plan', 'created_at', 'updated_at']
    
    def get_plan_details(self, obj):
        """Get plan details."""
        return {
            'id': str(obj.plan.id),
            'name': obj.plan.name,
            'slug': obj.plan.slug,
        }
    
    def get_is_over_limit_example(self, obj):
        """Example of over limit check."""
        # Use 80% of hard limit as example
        if obj.hard_limit:
            example_usage = int(obj.hard_limit * 0.8)
            return {
                'example_usage': example_usage,
                'is_over_limit': obj.is_over_limit(example_usage),
                'should_warn': obj.should_warn(example_usage),
            }
        return None
    
    def validate(self, attrs):
        """Validate quota data."""
        # Validate soft/hard limits
        hard_limit = attrs.get('hard_limit')
        soft_limit = attrs.get('soft_limit')
        
        if hard_limit is not None and soft_limit is not None:
            if soft_limit > hard_limit:
                raise serializers.ValidationError("Soft limit cannot exceed hard limit.")
        
        # Validate reset day
        reset_day = attrs.get('reset_day_of_month')
        if reset_day is not None:
            if reset_day < 1 or reset_day > 31:
                raise serializers.ValidationError("Reset day must be between 1 and 31.")
        
        # Validate warning threshold
        warning_threshold = attrs.get('warning_threshold')
        if warning_threshold is not None:
            if warning_threshold < 0 or warning_threshold > 100:
                raise serializers.ValidationError("Warning threshold must be between 0 and 100.")
        
        return attrs
