"""
A/B Testing Serializers

This module provides comprehensive serializers for A/B testing operations with
enterprise-grade validation, security, and performance optimization following
industry standards from Google Ads and OgAds.
"""

from typing import Optional, List, Dict, Any, Union, Tuple
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID
import json

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Sum, Count, Avg, Q, F
from django.db.models.functions import Coalesce

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.creative_model import Creative
from ..database_models.ab_testing_model import ABTest, TestVariant, TestResult, TestMetrics
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class ABTestSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for ABTest model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization with select_related
    - Type-safe Python code
    """
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    launched_by_name = serializers.CharField(source='launched_by.username', read_only=True)
    stopped_by_name = serializers.CharField(source='stopped_by.username', read_only=True)
    variant_count = serializers.SerializerMethodField()
    current_sample_size = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = ABTest
        fields = [
            'id', 'advertiser', 'advertiser_name', 'name', 'description',
            'test_type', 'traffic_allocation', 'confidence_level',
            'minimum_sample_size', 'maximum_duration_days', 'statistical_power',
            'effect_size_threshold', 'status', 'variant_count',
            'current_sample_size', 'progress_percentage', 'budget_spend',
            'security_checks_enabled', 'performance_monitoring_enabled',
            'created_at', 'updated_at', 'launched_at', 'stopped_at',
            'created_by', 'created_by_name', 'launched_by', 'launched_by_name',
            'stopped_by', 'stopped_by_name', 'stop_reason'
        ]
        read_only_fields = [
            'id', 'variant_count', 'current_sample_size', 'progress_percentage',
            'budget_spend', 'created_at', 'updated_at', 'launched_at', 'stopped_at',
            'created_by', 'launched_by', 'stopped_by', 'stop_reason'
        ]
    
    def get_variant_count(self, obj: ABTest) -> int:
        """Get variant count with optimized query."""
        try:
            return obj.testvariant_set.count()
        except Exception:
            return 0
    
    def get_current_sample_size(self, obj: ABTest) -> int:
        """Get current sample size with optimized query."""
        try:
            return obj.testvariant_set.aggregate(
                total=Coalesce(Sum('testresult__impressions'), 0)
            )['total'] or 0
        except Exception:
            return 0
    
    def get_progress_percentage(self, obj: ABTest) -> float:
        """Get progress percentage based on sample size."""
        try:
            current_size = self.get_current_sample_size(obj)
            return (current_size / obj.minimum_sample_size * 100) if obj.minimum_sample_size > 0 else 0
        except Exception:
            return 0.0
    
    def validate_name(self, value: str) -> str:
        """Validate test name with security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Test name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Test name contains prohibited characters")
        
        return value
    
    def validate_confidence_level(self, value: float) -> float:
        """Validate confidence level."""
        if not 0.8 <= value <= 0.99:
            raise serializers.ValidationError("Confidence level must be between 0.8 and 0.99")
        return value
    
    def validate_minimum_sample_size(self, value: int) -> int:
        """Validate minimum sample size."""
        if value < 100:
            raise serializers.ValidationError("Minimum sample size must be at least 100")
        if value > 1000000:
            raise serializers.ValidationError("Minimum sample size cannot exceed 1,000,000")
        return value
    
    def validate_maximum_duration_days(self, value: int) -> int:
        """Validate maximum duration."""
        if not 1 <= value <= 90:
            raise serializers.ValidationError("Maximum duration must be between 1 and 90 days")
        return value
    
    def validate_statistical_power(self, value: float) -> float:
        """Validate statistical power."""
        if not 0.5 <= value <= 0.99:
            raise serializers.ValidationError("Statistical power must be between 0.5 and 0.99")
        return value
    
    def validate_effect_size_threshold(self, value: float) -> float:
        """Validate effect size threshold."""
        if not 0.01 <= value <= 1.0:
            raise serializers.ValidationError("Effect size threshold must be between 0.01 and 1.0")
        return value
    
    def validate_traffic_allocation(self, value: Dict[str, float]) -> Dict[str, float]:
        """Validate traffic allocation with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Traffic allocation must be a dictionary")
        
        if not value:
            raise serializers.ValidationError("Traffic allocation cannot be empty")
        
        # Validate allocation values
        for variant_id, allocation in value.items():
            try:
                allocation_float = float(allocation)
                if not 0 <= allocation_float <= 1:
                    raise serializers.ValidationError(f"Allocation for variant {variant_id} must be between 0 and 1")
            except (ValueError, TypeError):
                raise serializers.ValidationError(f"Invalid allocation value for variant {variant_id}")
        
        # Check if allocation sums to 1.0 (allowing small floating point errors)
        total_allocation = sum(float(v) for v in value.values())
        if not (0.99 <= total_allocation <= 1.01):
            raise serializers.ValidationError("Traffic allocation must sum to 1.0")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with security checks."""
        # Security: Validate advertiser access
        advertiser = attrs.get('advertiser')
        if advertiser and hasattr(self, 'context') and 'request' in self.context:
            user = self.context['request'].user
            if not user.is_superuser and advertiser.user != user:
                raise serializers.ValidationError("User does not have access to this advertiser")
        
        # Validate test type
        test_type = attrs.get('test_type')
        valid_test_types = ['creative', 'landing_page', 'ad_copy', 'bidding', 'targeting']
        if test_type and test_type not in valid_test_types:
            raise serializers.ValidationError(f"Invalid test type. Must be one of: {valid_test_types}")
        
        return attrs


class ABTestCreateSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for creating A/B tests.
    
    Features:
    - Comprehensive input validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = ABTest
        fields = [
            'advertiser', 'name', 'description', 'test_type',
            'traffic_allocation', 'confidence_level', 'minimum_sample_size',
            'maximum_duration_days', 'statistical_power', 'effect_size_threshold',
            'security_checks_enabled', 'performance_monitoring_enabled'
        ]
    
    def validate_advertiser(self, value: Advertiser) -> Advertiser:
        """Validate advertiser with security checks."""
        try:
            user = self.context['request'].user
            
            # Security: Check user permissions
            if not user.is_superuser and value.user != user:
                raise serializers.ValidationError("User does not have access to this advertiser")
            
            # Security: Check if advertiser is active
            if value.is_deleted:
                raise serializers.ValidationError("Advertiser is not active")
            
            return value
            
        except Advertiser.DoesNotExist:
            raise serializers.ValidationError("Advertiser not found")
    
    def validate_name(self, value: str) -> str:
        """Validate test name with comprehensive security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Test name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters and patterns
        prohibited_patterns = [
            r'<script.*?>.*?</script>',  # Script tags
            r'javascript:',              # JavaScript protocol
            r'on\w+\s*=',                # Event handlers
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Test name contains prohibited content")
        
        return value
    
    def validate_traffic_allocation(self, value: Dict[str, float]) -> Dict[str, float]:
        """Validate traffic allocation with comprehensive checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Traffic allocation must be a dictionary")
        
        if not value:
            raise serializers.ValidationError("Traffic allocation cannot be empty")
        
        # Validate allocation values and variant IDs
        for variant_id, allocation in value.items():
            try:
                # Validate variant ID format
                UUID(str(variant_id))
                
                # Validate allocation value
                allocation_float = float(allocation)
                if not 0 <= allocation_float <= 1:
                    raise serializers.ValidationError(f"Allocation for variant {variant_id} must be between 0 and 1")
                
            except (ValueError, TypeError):
                raise serializers.ValidationError(f"Invalid allocation data for variant {variant_id}")
        
        # Check if allocation sums to 1.0 (allowing small floating point errors)
        total_allocation = sum(float(v) for v in value.values())
        if not (0.99 <= total_allocation <= 1.01):
            raise serializers.ValidationError("Traffic allocation must sum to 1.0")
        
        # Ensure minimum allocation per variant
        min_allocation = 0.01  # 1% minimum
        for variant_id, allocation in value.items():
            if float(allocation) < min_allocation:
                raise serializers.ValidationError(f"Variant {variant_id} allocation must be at least {min_allocation}")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Validate minimum sample size vs maximum duration
        min_sample_size = attrs.get('minimum_sample_size', 1000)
        max_duration = attrs.get('maximum_duration_days', 30)
        
        # Business logic: Ensure reasonable sample size for duration
        if min_sample_size > 100000 and max_duration < 7:
            raise serializers.ValidationError("Large sample sizes require longer duration")
        
        # Validate statistical parameters consistency
        confidence_level = attrs.get('confidence_level', 0.95)
        statistical_power = attrs.get('statistical_power', 0.8)
        
        if confidence_level > 0.95 and statistical_power > 0.9:
            raise serializers.ValidationError("High confidence and power may require very large sample sizes")
        
        return attrs


class TestVariantSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for TestVariant model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    test_name = serializers.CharField(source='test.name', read_only=True)
    advertiser_name = serializers.CharField(source='test.advertiser.company_name', read_only=True)
    current_metrics = serializers.SerializerMethodField()
    
    class Meta:
        model = TestVariant
        fields = [
            'id', 'test', 'test_name', 'advertiser_name', 'name', 'description',
            'is_control', 'configuration', 'traffic_allocation', 'status',
            'current_metrics', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'current_metrics', 'created_at', 'updated_at']
    
    def get_current_metrics(self, obj: TestVariant) -> Dict[str, Any]:
        """Get current metrics with optimized query."""
        try:
            # Performance: Use optimized aggregate query
            results = obj.testresult_set.aggregate(
                impressions=Coalesce(Sum('impressions'), 0),
                clicks=Coalesce(Sum('clicks'), 0),
                conversions=Coalesce(Sum('conversions'), 0),
                revenue=Coalesce(Sum('revenue'), Decimal('0.00'))
            )
            
            impressions = results['impressions'] or 0
            clicks = results['clicks'] or 0
            conversions = results['conversions'] or 0
            revenue = results['revenue'] or Decimal('0.00')
            
            # Calculate rates
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            conversion_rate = (conversions / clicks * 100) if clicks > 0 else 0
            
            return {
                'impressions': impressions,
                'clicks': clicks,
                'conversions': conversions,
                'revenue': float(revenue),
                'ctr': round(ctr, 2),
                'conversion_rate': round(conversion_rate, 2)
            }
            
        except Exception:
            return {
                'impressions': 0, 'clicks': 0, 'conversions': 0,
                'revenue': 0.0, 'ctr': 0.0, 'conversion_rate': 0.0
            }
    
    def validate_name(self, value: str) -> str:
        """Validate variant name with security checks."""
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError("Variant name must be at least 2 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Variant name contains prohibited characters")
        
        return value
    
    def validate_configuration(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate variant configuration with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Configuration must be a dictionary")
        
        # Security: Check for prohibited content
        config_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, config_str, re.IGNORECASE):
                raise serializers.ValidationError("Configuration contains prohibited content")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        test = attrs.get('test')
        is_control = attrs.get('is_control', False)
        
        # Business logic: Ensure only one control variant per test
        if test and is_control:
            existing_control = test.testvariant_set.filter(is_control=True).exists()
            if self.instance and self.instance.is_control:
                # Allow updating existing control variant
                pass
            elif existing_control:
                raise serializers.ValidationError("Test already has a control variant")
        
        # Security: Validate user access to test
        if test and hasattr(self, 'context') and 'request' in self.context:
            user = self.context['request'].user
            if not user.is_superuser and test.advertiser.user != user:
                raise serializers.ValidationError("User does not have access to this test")
        
        return attrs


class TestVariantCreateSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for creating test variants.
    
    Features:
    - Comprehensive input validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = TestVariant
        fields = [
            'test', 'name', 'description', 'is_control', 'configuration'
        ]
    
    def validate_test(self, value: ABTest) -> ABTest:
        """Validate test with security checks."""
        try:
            user = self.context['request'].user
            
            # Security: Check user permissions
            if not user.is_superuser and value.advertiser.user != user:
                raise serializers.ValidationError("User does not have access to this test")
            
            # Business logic: Check test status
            if value.status not in ['draft', 'setup']:
                raise serializers.ValidationError("Variants can only be added to tests in draft or setup status")
            
            return value
            
        except ABTest.DoesNotExist:
            raise serializers.ValidationError("Test not found")
    
    def validate_configuration(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate variant configuration with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Configuration must be a dictionary")
        
        # Validate configuration structure based on test type
        if hasattr(self, 'context') and 'request' in self.context:
            test_id = self.initial_data.get('test')
            if test_id:
                try:
                    test = ABTest.objects.get(id=test_id)
                    TestVariantCreateSerializer._validate_configuration_by_type(value, test.test_type)
                except ABTest.DoesNotExist:
                    pass  # Will be caught by test validation
        
        # Security: Check for prohibited content
        config_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, config_str, re.IGNORECASE):
                raise serializers.ValidationError("Configuration contains prohibited content")
        
        return value
    
    @staticmethod
    def _validate_configuration_by_type(config: Dict[str, Any], test_type: str) -> None:
        """Validate configuration based on test type."""
        if test_type == 'creative':
            required_fields = ['creative_id', 'creative_type']
            TestVariantCreateSerializer._validate_required_fields(config, required_fields)
            
        elif test_type == 'landing_page':
            required_fields = ['landing_page_url', 'page_elements']
            TestVariantCreateSerializer._validate_required_fields(config, required_fields)
            
        elif test_type == 'ad_copy':
            required_fields = ['headline', 'description', 'call_to_action']
            TestVariantCreateSerializer._validate_required_fields(config, required_fields)
            
        elif test_type == 'bidding':
            required_fields = ['bid_strategy', 'bid_amount']
            TestVariantCreateSerializer._validate_required_fields(config, required_fields)
            
        elif test_type == 'targeting':
            required_fields = ['targeting_criteria', 'audience_segments']
            TestVariantCreateSerializer._validate_required_fields(config, required_fields)
    
    @staticmethod
    def _validate_required_fields(config: Dict[str, Any], required_fields: List[str]) -> None:
        """Validate required fields in configuration."""
        missing_fields = [field for field in required_fields if field not in config]
        if missing_fields:
            raise serializers.ValidationError(f"Missing required fields: {missing_fields}")


class TestResultSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for TestResult model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    test_name = serializers.CharField(source='variant.test.name', read_only=True)
    advertiser_name = serializers.CharField(source='variant.test.advertiser.company_name', read_only=True)
    
    class Meta:
        model = TestResult
        fields = [
            'id', 'variant', 'variant_name', 'test_name', 'advertiser_name',
            'impressions', 'clicks', 'conversions', 'revenue',
            'custom_metrics', 'recorded_at'
        ]
        read_only_fields = ['id', 'recorded_at']
    
    def validate_impressions(self, value: int) -> int:
        """Validate impressions with business logic checks."""
        if value < 0:
            raise serializers.ValidationError("Impressions cannot be negative")
        
        # Performance: Set reasonable limits
        if value > 10000000:
            raise serializers.ValidationError("Impressions value seems unusually high")
        
        return value
    
    def validate_clicks(self, value: int) -> int:
        """Validate clicks with business logic checks."""
        if value < 0:
            raise serializers.ValidationError("Clicks cannot be negative")
        
        # Performance: Set reasonable limits
        if value > 1000000:
            raise serializers.ValidationError("Clicks value seems unusually high")
        
        # Business logic: Clicks cannot exceed impressions
        impressions = self.initial_data.get('impressions', 0)
        if impressions and value > impressions:
            raise serializers.ValidationError("Clicks cannot exceed impressions")
        
        return value
    
    def validate_conversions(self, value: int) -> int:
        """Validate conversions with business logic checks."""
        if value < 0:
            raise serializers.ValidationError("Conversions cannot be negative")
        
        # Performance: Set reasonable limits
        if value > 100000:
            raise serializers.ValidationError("Conversions value seems unusually high")
        
        # Business logic: Conversions cannot exceed clicks
        clicks = self.initial_data.get('clicks', 0)
        if clicks and value > clicks:
            raise serializers.ValidationError("Conversions cannot exceed clicks")
        
        return value
    
    def validate_revenue(self, value: Decimal) -> Decimal:
        """Validate revenue with business logic checks."""
        if value < 0:
            raise serializers.ValidationError("Revenue cannot be negative")
        
        # Performance: Set reasonable limits
        if value > Decimal('1000000'):
            raise serializers.ValidationError("Revenue value seems unusually high")
        
        return value
    
    def validate_custom_metrics(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate custom metrics with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Custom metrics must be a dictionary")
        
        # Security: Check for prohibited content
        metrics_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, metrics_str, re.IGNORECASE):
                raise serializers.ValidationError("Custom metrics contain prohibited content")
        
        # Validate metric values
        for metric_name, metric_value in value.items():
            if not isinstance(metric_name, str) or len(metric_name.strip()) < 1:
                raise serializers.ValidationError("Invalid metric name")
            
            try:
                # Ensure metric values are numeric
                float(metric_value)
            except (ValueError, TypeError):
                raise serializers.ValidationError(f"Invalid metric value for {metric_name}")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Security: Validate user access to variant
        variant = attrs.get('variant')
        if variant and hasattr(self, 'context') and 'request' in self.context:
            user = self.context['request'].user
            if not user.is_superuser and variant.test.advertiser.user != user:
                raise serializers.ValidationError("User does not have access to this variant")
        
        return attrs


class TestMetricsSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for TestMetrics model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    test_name = serializers.CharField(source='test.name', read_only=True)
    advertiser_name = serializers.CharField(source='test.advertiser.company_name', read_only=True)
    
    class Meta:
        model = TestMetrics
        fields = [
            'id', 'test', 'test_name', 'advertiser_name', 'metric_type',
            'metric_value', 'baseline_value', 'improvement_percentage',
            'statistical_significance', 'confidence_interval', 'calculated_at'
        ]
        read_only_fields = ['id', 'calculated_at']
    
    def validate_metric_value(self, value: float) -> float:
        """Validate metric value."""
        try:
            metric_float = float(value)
            if not -1000 <= metric_float <= 1000000:
                raise serializers.ValidationError("Metric value out of reasonable range")
            return metric_float
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid metric value")
    
    def validate_baseline_value(self, value: float) -> float:
        """Validate baseline value."""
        try:
            baseline_float = float(value)
            if not -1000 <= baseline_float <= 1000000:
                raise serializers.ValidationError("Baseline value out of reasonable range")
            return baseline_float
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid baseline value")
    
    def validate_improvement_percentage(self, value: float) -> float:
        """Validate improvement percentage."""
        try:
            improvement_float = float(value)
            if not -100 <= improvement_float <= 10000:
                raise serializers.ValidationError("Improvement percentage out of reasonable range")
            return improvement_float
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid improvement percentage")
    
    def validate_statistical_significance(self, value: bool) -> bool:
        """Validate statistical significance."""
        return bool(value)
    
    def validate_confidence_interval(self, value: Dict[str, float]) -> Dict[str, float]:
        """Validate confidence interval."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Confidence interval must be a dictionary")
        
        required_keys = ['lower', 'upper']
        for key in required_keys:
            if key not in value:
                raise serializers.ValidationError(f"Missing {key} bound in confidence interval")
            
            try:
                bound_float = float(value[key])
                if not -1000 <= bound_float <= 1000000:
                    raise serializers.ValidationError(f"Confidence interval {key} bound out of reasonable range")
            except (ValueError, TypeError):
                raise serializers.ValidationError(f"Invalid {key} bound in confidence interval")
        
        # Validate interval logic
        if value['lower'] > value['upper']:
            raise serializers.ValidationError("Lower bound cannot be greater than upper bound")
        
        return value


# Request/Response Serializers for API Endpoints

class ABTestLaunchRequestSerializer(serializers.Serializer):
    """Serializer for A/B test launch requests."""
    
    launch_options = serializers.DictField(required=False, default=dict)
    
    def validate_launch_options(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate launch options."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Launch options must be a dictionary")
        
        # Validate launch option keys
        valid_options = ['immediate_launch', 'gradual_rollout', 'monitoring_level']
        for option in value.keys():
            if option not in valid_options:
                raise serializers.ValidationError(f"Invalid launch option: {option}")
        
        return value


class ABTestStopRequestSerializer(serializers.Serializer):
    """Serializer for A/B test stop requests."""
    
    stop_reason = serializers.CharField(max_length=500, required=True)
    save_results = serializers.BooleanField(default=True)
    
    def validate_stop_reason(self, value: str) -> str:
        """Validate stop reason."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Stop reason must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'"]
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Stop reason contains prohibited characters")
        
        return value


class ABTestAnalysisRequestSerializer(serializers.Serializer):
    """Serializer for A/B test analysis requests."""
    
    analysis_type = serializers.ChoiceField(
        choices=['comprehensive', 'statistical', 'bayesian'],
        default='comprehensive'
    )
    include_recommendations = serializers.BooleanField(default=True)
    confidence_level = serializers.FloatField(min_value=0.8, max_value=0.99, default=0.95)
    
    def validate_confidence_level(self, value: float) -> float:
        """Validate confidence level."""
        if not 0.8 <= value <= 0.99:
            raise serializers.ValidationError("Confidence level must be between 0.8 and 0.99")
        return value


class ABTestPerformanceResponseSerializer(serializers.Serializer):
    """Serializer for A/B test performance responses."""
    
    test_id = serializers.UUIDField()
    test_name = serializers.CharField()
    test_type = serializers.CharField()
    status = serializers.CharField()
    overall_metrics = serializers.DictField()
    variant_performance = serializers.ListField(child=serializers.DictField())
    test_progress = serializers.DictField()
    generated_at = serializers.DateTimeField()


class ABTestStatisticsResponseSerializer(serializers.Serializer):
    """Serializer for A/B test statistics responses."""
    
    total_tests = serializers.IntegerField()
    active_tests = serializers.IntegerField()
    completed_tests = serializers.IntegerField()
    draft_tests = serializers.IntegerField()
    tests_by_type = serializers.ListField(child=serializers.DictField())
    tests_by_status = serializers.ListField(child=serializers.DictField())
    average_duration_days = serializers.FloatField()
    success_rate = serializers.FloatField()
    generated_at = serializers.DateTimeField()


class TestVariantMetricsResponseSerializer(serializers.Serializer):
    """Serializer for test variant metrics responses."""
    
    variant_id = serializers.UUIDField()
    variant_name = serializers.CharField()
    test_name = serializers.CharField()
    is_control = serializers.BooleanField()
    metrics = serializers.DictField()
    performance_vs_control = serializers.DictField()
    generated_at = serializers.DateTimeField()


class TestAnalyticsDashboardResponseSerializer(serializers.Serializer):
    """Serializer for test analytics dashboard responses."""
    
    summary = serializers.DictField()
    recent_tests = serializers.ListField(child=serializers.DictField())
    top_performing_tests = serializers.ListField(child=serializers.DictField())
    quick_stats = serializers.DictField()
    generated_at = serializers.DateTimeField()


class TestAnalyticsTrendsResponseSerializer(serializers.Serializer):
    """Serializer for test analytics trends responses."""
    
    period_days = serializers.IntegerField()
    test_creation_trend = serializers.ListField(child=serializers.DictField())
    success_rate_trend = serializers.ListField(child=serializers.DictField())


# Comprehensive Response Serializers

class ABTestCreateResponseSerializer(serializers.Serializer):
    """Serializer for A/B test creation responses."""
    
    id = serializers.UUIDField()
    advertiser_id = serializers.UUIDField()
    name = serializers.CharField()
    test_type = serializers.CharField()
    traffic_allocation = serializers.DictField()
    confidence_level = serializers.FloatField()
    minimum_sample_size = serializers.IntegerField()
    maximum_duration_days = serializers.IntegerField()
    statistical_power = serializers.FloatField()
    effect_size_threshold = serializers.FloatField()
    status = serializers.CharField()
    security_checks_enabled = serializers.BooleanField()
    performance_monitoring_enabled = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    created_by = serializers.CharField(allow_null=True)


class ABTestLaunchResponseSerializer(serializers.Serializer):
    """Serializer for A/B test launch responses."""
    
    message = serializers.CharField()
    test_id = serializers.UUIDField()
    status = serializers.CharField()
    launched_at = serializers.DateTimeField()


class ABTestStopResponseSerializer(serializers.Serializer):
    """Serializer for A/B test stop responses."""
    
    message = serializers.CharField()
    test_id = serializers.UUIDField()
    status = serializers.CharField()
    stop_reason = serializers.CharField()
    stopped_at = serializers.DateTimeField()


class ABTestAnalysisResponseSerializer(serializers.Serializer):
    """Serializer for A/B test analysis responses."""
    
    test_id = serializers.UUIDField()
    test_name = serializers.CharField()
    analysis_type = serializers.CharField()
    total_sample_size = serializers.IntegerField()
    variants = serializers.ListField(child=serializers.DictField())
    statistical_significance = serializers.DictField()
    recommendations = serializers.ListField(child=serializers.CharField())


class TestVariantListResponseSerializer(serializers.Serializer):
    """Serializer for test variant list responses."""
    
    test_id = serializers.UUIDField()
    test_name = serializers.CharField()
    variants = serializers.ListField(child=serializers.DictField())
