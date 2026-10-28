# api/cms/resources.py
"""API resources for CMS - DRF serializers and viewsets."""
import logging
from typing import Any, Dict, List, Optional, Type
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers, viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.fields import SerializerMethodField
from rest_framework.validators import UniqueValidator
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes

from .pagination import (
    CMSPagePagination, CMSSurveyPagination, CMSRewardPagination,
    CMSUserPagination, CMSAnalyticsPagination
)
from .throttling import (
    CMSUserThrottle, SurveyThrottle, RewardThrottle,
    PayoutThrottle, CMSAnonThrottle
)

logger = logging.getLogger(__name__)
User = get_user_model()


# ── Original Import-Export Resources (Enhanced) ─────────────────────────────────────

try:
    from import_export import resources, fields
    from import_export.widgets import ForeignKeyWidget, JSONWidget
    HAS_IMPORT_EXPORT = True
except ImportError:
    HAS_IMPORT_EXPORT = False
    # Stubs
    class resources:
        class ModelResource:
            pass
    class fields:
        class Field:
            def __init__(self, *a, **kw): pass
    class ForeignKeyWidget:
        def __init__(self, *a, **kw): pass

if HAS_IMPORT_EXPORT:
    class ConversionLogResource(resources.ModelResource):
        class Meta:
            from api.cms.models_new.cpalead import ConversionLog
            model = ConversionLog
            fields = ['id', 'subid', 'lead_id', 'payout_usd', 'campaign_id',
                      'status', 'virtual_amount_awarded', 'created_at']
            export_order = ['id', 'created_at', 'subid', 'lead_id',
                            'payout_usd', 'status', 'virtual_amount_awarded']

    class WithdrawalRequestResource(resources.ModelResource):
        username = fields.Field(attribute='user__username', column_name='username')

        class Meta:
            from api.cms.models_new.withdrawal import WithdrawalRequest
            model = WithdrawalRequest
            fields = ['id', 'username', 'method', 'requested_coins', 'requested_usd',
                      'net_usd', 'status', 'created_at', 'paid_at']
            export_order = ['id', 'created_at', 'username', 'method',
                            'requested_usd', 'net_usd', 'status', 'paid_at']

    class ReferralEarningResource(resources.ModelResource):
        referrer_name = fields.Field(attribute='referrer__username', column_name='referrer')
        referred_name = fields.Field(attribute='referred__username', column_name='referred')

        class Meta:
            from api.cms.models_new.referral import ReferralEarning
            model = ReferralEarning


# ── Enhanced API Resources ─────────────────────────────────────

class BaseCMSSerializer(serializers.ModelSerializer):
    """Base serializer for CMS models."""
    
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    def validate(self, attrs):
        """Common validation logic."""
        # Add any common validation here
        return super().validate(attrs)


class TimestampedSerializer(BaseCMSSerializer):
    """Serializer for models with timestamp fields."""
    
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class SoftDeleteSerializer(BaseCMSSerializer):
    """Serializer for models with soft delete functionality."""
    
    is_deleted = serializers.BooleanField(read_only=True)
    deleted_at = serializers.DateTimeField(read_only=True)


# ── User Serializers ─────────────────────────────────────

class UserSerializer(BaseCMSSerializer):
    """Serializer for User model."""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                 'is_staff', 'is_active', 'date_joined', 'last_login']
        read_only_fields = ['id', 'date_joined', 'last_login', 'is_staff']


class UserDetailSerializer(UserSerializer):
    """Detailed user serializer with profile information."""
    
    profile_completeness = SerializerMethodField()
    total_surveys = SerializerMethodField()
    total_earned = SerializerMethodField()
    
    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ['profile_completeness', 'total_surveys', 'total_earned']
    
    def get_profile_completeness(self, obj) -> Optional[float]:
        """Get profile completeness percentage."""
        try:
            return obj.userprofile.completeness_percentage
        except (User.userprofile.RelatedObjectDoesNotExist, AttributeError):
            return None
    
    def get_total_surveys(self, obj) -> int:
        """Get total surveys completed."""
        return obj.survey_completions.filter(status='completed').count()
    
    def get_total_earned(self, obj) -> float:
        """Get total amount earned."""
        from django.db.models import Sum
        return obj.reward_transactions.filter(
            transaction_type='earned', status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for user creation."""
    
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password', 'password_confirm']
    
    def validate(self, attrs):
        """Validate password confirmation."""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs
    
    def create(self, validated_data):
        """Create user with hashed password."""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


# ── Survey Serializers ─────────────────────────────────────

class SurveyCategorySerializer(BaseCMSSerializer):
    """Serializer for SurveyCategory model."""
    
    class Meta:
        model = 'SurveyCategory'
        fields = ['id', 'name', 'description', 'is_active', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class SurveySerializer(BaseCMSSerializer):
    """Serializer for Survey model."""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    participant_count = SerializerMethodField()
    completion_count = SerializerMethodField()
    avg_quality_score = SerializerMethodField()
    is_available = SerializerMethodField()
    
    class Meta:
        model = 'SurveyTemplate'
        fields = [
            'id', 'uuid', 'title', 'description', 'category', 'category_name',
            'difficulty', 'status', 'is_public', 'min_reward', 'max_reward',
            'estimated_time', 'max_participants', 'current_participants',
            'participant_count', 'completion_count', 'avg_quality_score',
            'is_available', 'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'current_participants', 'created_by', 'created_at', 'updated_at']
    
    def get_participant_count(self, obj) -> int:
        """Get total participant count."""
        return obj.survey_completions.count()
    
    def get_completion_count(self, obj) -> int:
        """Get completion count."""
        return obj.survey_completions.filter(status='completed').count()
    
    def get_avg_quality_score(self, obj) -> Optional[float]:
        """Get average quality score."""
        from django.db.models import Avg
        return obj.survey_completions.filter(status='completed').aggregate(
            avg=Avg('quality_score')
        )['avg']
    
    def get_is_available(self, obj) -> bool:
        """Check if survey is available to current user."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return obj.is_public and obj.status == 'active'
        
        # Check if user has already completed this survey
        completed = obj.survey_completions.filter(
            user=request.user, status='completed'
        ).exists()
        
        return obj.is_public and obj.status == 'active' and not completed


class SurveyCompletionSerializer(BaseCMSSerializer):
    """Serializer for SurveyCompletion model."""
    
    survey_title = serializers.CharField(source='survey.title', read_only=True)
    duration_seconds = SerializerMethodField()
    reward_earned = SerializerMethodField()
    
    class Meta:
        model = 'SurveyCompletion'
        fields = [
            'id', 'uuid', 'user', 'survey', 'survey_title', 'status',
            'responses', 'quality_score', 'started_at', 'completed_at',
            'duration_seconds', 'reward_earned', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'user', 'created_at', 'updated_at']
    
    def get_duration_seconds(self, obj) -> Optional[int]:
        """Calculate duration in seconds."""
        if obj.started_at and obj.completed_at:
            return int((obj.completed_at - obj.started_at).total_seconds())
        return None
    
    def get_reward_earned(self, obj) -> float:
        """Get reward amount earned."""
        from django.db.models import Sum
        return obj.reward_transactions.filter(
            transaction_type='earned', status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0


# ── Reward Serializers ─────────────────────────────────────

class RewardTransactionSerializer(BaseCMSSerializer):
    """Serializer for RewardTransaction model."""
    
    pool_name = serializers.CharField(source='reward_pool.name', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = 'RewardTransaction'
        fields = [
            'id', 'uuid', 'user', 'username', 'reward_pool', 'pool_name',
            'amount', 'transaction_type', 'status', 'description',
            'data', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'user', 'created_at', 'updated_at']


class UserProfileSerializer(BaseCMSSerializer):
    """Serializer for UserProfile model."""
    
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    age = SerializerMethodField()
    
    class Meta:
        model = 'UserProfile'
        fields = [
            'id', 'uuid', 'user', 'username', 'email', 'first_name',
            'last_name', 'phone_number', 'date_of_birth', 'age', 'address',
            'country', 'city', 'postal_code', 'avatar_url', 'bio',
            'preferences', 'completeness_percentage', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'user', 'created_at', 'updated_at']
    
    def get_age(self, obj) -> Optional[int]:
        """Calculate age from date of birth."""
        if obj.date_of_birth:
            today = timezone.now().date()
            return today.year - obj.date_of_birth.year - (
                (today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day)
            )
        return None


# ── Resource Utilities ─────────────────────────────────────

class ResourceUtils:
    """Utilities for working with API resources."""
    
    @staticmethod
    def get_serializer_fields(serializer_class: Type[serializers.Serializer]) -> List[str]:
        """Get field names from serializer class."""
        if hasattr(serializer_class, 'Meta'):
            return list(serializer_class.Meta.fields)
        return list(serializer_class().fields.keys())
    
    @staticmethod
    def validate_serializer_data(serializer_class: Type[serializers.Serializer], data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data using serializer."""
        serializer = serializer_class(data=data)
        if serializer.is_valid():
            return serializer.validated_data
        return {'errors': serializer.errors}
    
    @staticmethod
    def create_response(data: Any, status_code: int = status.HTTP_200_OK, 
                      metadata: Dict[str, Any] = None) -> Response:
        """Create standardized API response."""
        response_data = {'data': data}
        if metadata:
            response_data['metadata'] = metadata
        
        return Response(response_data, status=status_code)
    
    @staticmethod
    def create_error_response(message: str, status_code: int = status.HTTP_400_BAD_REQUEST,
                          errors: Dict[str, Any] = None) -> Response:
        """Create standardized error response."""
        response_data = {'error': message}
        if errors:
            response_data['errors'] = errors
        
        return Response(response_data, status=status_code)
    
    @staticmethod
    def paginate_response(queryset, request, serializer_class: Type[serializers.Serializer],
                        pagination_class: Type = CMSPagePagination) -> Response:
        """Paginate queryset and return response."""
        paginator = pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = serializer_class(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)
    logger.info("[Resources] django-import-export not installed. pip install django-import-export")

    class ConversionLogResource: pass
    class WithdrawalRequestResource: pass
    class ReferralEarningResource: pass
    class LeaderboardEntryResource: pass
    class QuizAttemptResource: pass
