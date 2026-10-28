# api/cms/serializers_new/UserProfileSerializer.py
"""
Serializers for User Profile and Segmentation Models
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models_new.user_profile import UserProfile, UserSegment
from ..models_new.profile_surveys import SurveyCompletion, SurveyTemplate

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    """Basic user profile serializer"""
    class Meta:
        model = UserProfile
        fields = [
            'uuid', 'user', 'date_of_birth', 'gender', 'country',
            'education', 'income_level', 'interests', 'hobbies',
            'primary_language', 'additional_languages', 'primary_device',
            'operating_system', 'browser_preference',
            'survey_frequency_preference', 'email_notifications',
            'push_notifications', 'sms_notifications',
            'marketing_communications', 'profile_completeness',
            'last_activity_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class UserProfileDetailSerializer(serializers.ModelSerializer):
    """Detailed user profile serializer with relationships"""
    age = serializers.SerializerMethodField()
    interests_list = serializers.SerializerMethodField()
    profile_completeness_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = [
            'uuid', 'user', 'date_of_birth', 'age', 'gender', 'country',
            'state_province', 'city', 'postal_code', 'timezone',
            'education', 'income_level', 'occupation', 'industry',
            'primary_language', 'additional_languages', 'interests', 'hobbies',
            'preferred_survey_categories', 'survey_frequency_preference',
            'primary_device', 'operating_system', 'browser_preference',
            'survey_participation_score', 'average_completion_time',
            'quality_score', 'email_notifications', 'push_notifications',
            'sms_notifications', 'marketing_communications',
            'profile_completeness', 'profile_completeness_percentage',
            'last_activity_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def get_age(self, obj):
        """Calculate age from date of birth"""
        if obj.date_of_birth:
            from datetime import date
            today = date.today()
            return today.year - obj.date_of_birth.year - (
                (today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day)
            )
        return None
    
    def get_interests_list(self, obj):
        """Return interests as a list"""
        return obj.interests if obj.interests else []
    
    def get_profile_completeness_percentage(self, obj):
        """Return profile completeness as percentage"""
        return f"{obj.profile_completeness or 0:.1f}%"


class UserSegmentSerializer(serializers.ModelSerializer):
    """User segment serializer"""
    user_count_display = serializers.SerializerMethodField()
    matching_users_count = serializers.SerializerMethodField()
    
    class Meta:
        model = UserSegment
        fields = [
            'uuid', 'name', 'description', 'age_min', 'age_max',
            'genders', 'countries', 'education_levels', 'income_levels',
            'interests', 'languages', 'min_participation_score',
            'min_quality_score', 'max_avg_completion_time',
            'is_active', 'user_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def get_user_count_display(self, obj):
        """Display user count with formatting"""
        if obj.user_count:
            return f"{obj.user_count:,} users"
        return "0 users"
    
    def get_matching_users_count(self, obj):
        """Get count of matching users"""
        return obj.get_matching_users().count()


class UserSegmentDetailSerializer(serializers.ModelSerializer):
    """Detailed user segment serializer with relationships"""
    matching_users = serializers.SerializerMethodField()
    top_earners = serializers.SerializerMethodField()
    
    class Meta:
        model = UserSegment
        fields = [
            'uuid', 'name', 'description', 'age_min', 'age_max',
            'genders', 'countries', 'education_levels', 'income_levels',
            'interests', 'languages', 'min_participation_score',
            'min_quality_score', 'max_avg_completion_time',
            'is_active', 'user_count', 'depends_on',
            'matching_users', 'top_earners', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def get_matching_users(self, obj):
        """Get matching users with basic info"""
        matching_users = obj.get_matching_users()[:10]  # Limit to 10 for performance
        return UserProfileSerializer(matching_users, many=True).data
    
    def get_top_earners(self, obj):
        """Get top earners in this segment"""
        matching_users = obj.get_matching_users()
        top_earners = sorted(
            matching_users,
            key=lambda x: x.survey_participation_score or 0,
            reverse=True
        )[:5]
        
        return UserProfileSerializer(top_earners, many=True).data


class UserSegmentCreateSerializer(serializers.ModelSerializer):
    """User segment creation serializer"""
    class Meta:
        model = UserSegment
        fields = [
            'name', 'description', 'age_min', 'age_max',
            'genders', 'countries', 'education_levels', 'income_levels',
            'interests', 'languages', 'min_participation_score',
            'min_quality_score', 'max_avg_completion_time'
        ]
    
    def validate_age_range(self, data):
        """Validate that min_age <= max_age"""
        if data.get('age_min') and data.get('age_max'):
            if data['age_min'] > data['age_max']:
                raise serializers.ValidationError(
                    "Minimum age cannot be greater than maximum age"
                )
        return data
    
    def validate_interests(self, data):
        """Validate interests field"""
        interests = data.get('interests', [])
        if not isinstance(interests, list):
            raise serializers.ValidationError("Interests must be a list")
        
        # Check for valid interest values
        valid_interests = ['technology', 'gaming', 'sports', 'education', 'entertainment', 'business', 'health', 'travel']
        for interest in interests:
            if interest not in valid_interests:
                raise serializers.ValidationError(
                    f"Invalid interest: {interest}. Valid interests: {valid_interests}"
                )
        
        return data


class SurveyCompletionSerializer(serializers.ModelSerializer):
    """Survey completion serializer for user profiles"""
    survey_title = serializers.CharField(source='survey.title', read_only=True)
    survey_uuid = serializers.UUIDField(source='survey.uuid', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    time_spent_minutes = serializers.SerializerMethodField()
    
    class Meta:
        model = SurveyCompletion
        fields = [
            'uuid', 'survey', 'user', 'status', 'started_at',
            'completed_at', 'time_spent_seconds', 'quality_score',
            'total_reward_earned', 'survey_title', 'survey_uuid',
            'user_username', 'time_spent_minutes'
        ]
        read_only_fields = ['uuid', 'started_at', 'completed_at', 'survey_title', 'survey_uuid', 'user_username']
    
    def get_time_spent_minutes(self, obj):
        """Convert seconds to minutes"""
        if obj.time_spent_seconds:
            return round(obj.time_spent_seconds / 60, 1)
        return 0


class UserSegmentAnalyticsSerializer(serializers.Serializer):
    """User segment analytics serializer"""
    segment_info = serializers.SerializerMethodField()
    survey_activity = serializers.SerializerMethodField()
    earnings = serializers.SerializerMethodField()
    demographics = serializers.SerializerMethodField()
    
    def __init__(self, *args, **kwargs):
        self.segment = kwargs.get('segment', None)
        super().__init__(*args, **kwargs)
    
    def get_segment_info(self, obj):
        """Get segment information"""
        if self.segment:
            return {
                'uuid': str(self.segment.uuid),
                'name': self.segment.name,
                'user_count': self.segment.user_count
            }
        return {}
    
    def get_survey_activity(self, obj):
        """Get survey activity for segment"""
        # This would be populated by the service
        return obj.get('survey_activity', {})
    
    def get_earnings(self, obj):
        """Get earnings information"""
        # This would be populated by the service
        return obj.get('earnings', {})
    
    def get_demographics(self, obj):
        """Get demographic breakdown"""
        # This would be populated by the service
        return obj.get('demographics', {})


# ─────────────────────────────────────────────────────────────────────────────
# PART 7 ADDITION — UserSessionSerializer
# ─────────────────────────────────────────────────────────────────────────────

class UserSessionSerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source='user', read_only=True)

    class Meta:
        from api.cms.models_new.sessions import UserSession
        model = UserSession
        fields = [
            'id', 'user', 'user_display', 'ip_address', 'user_agent',
            'device_type', 'is_active', 'started_at', 'ended_at',
            'session_duration_seconds',
        ]
        read_only_fields = ['id', 'user', 'started_at', 'session_duration_seconds']
