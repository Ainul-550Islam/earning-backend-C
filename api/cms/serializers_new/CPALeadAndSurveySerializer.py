# api/cms/serializers_new/CPALeadAndSurveySerializer.py
"""
Serializers for CPAlead Locker, ZeroHours, and Survey Profile Models
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models_new.cpalead import LockerUnlock, ZeroHoursSessionLog
from ..models_new.profile_surveys import (
    SurveyCategory, SurveyTemplate, SurveyQuestion, SurveyCompletion, SurveyResponse
)

User = get_user_model()


# ── CPAlead Models ─────────────────────────────────────────────────────────────

class LockerUnlockSerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source='user', read_only=True)

    class Meta:
        model = LockerUnlock
        fields = [
            'uuid', 'locker', 'user', 'user_display', 'session_key',
            'unlock_source', 'unlocked_at', 'expires_at', 'is_valid',
        ]
        read_only_fields = ['uuid', 'unlocked_at', 'is_valid']


class ZeroHoursSessionLogSerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source='user', read_only=True)

    class Meta:
        model = ZeroHoursSessionLog
        fields = [
            'uuid', 'session_id', 'locker', 'user', 'user_display',
            'session_key', 'started_at', 'completed_at', 'duration_seconds',
        ]
        read_only_fields = ['uuid', 'duration_seconds']


# ── Profile Surveys ────────────────────────────────────────────────────────────

class SurveyCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyCategory
        fields = [
            'uuid', 'name', 'slug', 'description', 'icon',
            'min_age', 'max_age', 'target_genders',
        ]
        read_only_fields = ['uuid']


class SurveyQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyQuestion
        fields = [
            'uuid', 'survey', 'question_text', 'question_type',
            'help_text', 'is_required', 'order', 'choices',
        ]
        read_only_fields = ['uuid']


class SurveyTemplateSerializer(serializers.ModelSerializer):
    questions = SurveyQuestionSerializer(many=True, read_only=True)
    category_display = serializers.StringRelatedField(source='category', read_only=True)

    class Meta:
        model = SurveyTemplate
        fields = [
            'uuid', 'title', 'description', 'category', 'category_display',
            'survey_type', 'status', 'min_age', 'max_age', 'questions',
        ]
        read_only_fields = ['uuid']


class SurveyResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyResponse
        fields = [
            'uuid', 'completion', 'question', 'answer', 'answer_text',
            'answer_number', 'response_time_seconds', 'is_attention_check',
        ]
        read_only_fields = ['uuid']


class SurveyCompletionSerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source='user', read_only=True)
    responses = SurveyResponseSerializer(many=True, read_only=True)

    class Meta:
        model = SurveyCompletion
        fields = [
            'uuid', 'survey', 'user', 'user_display',
            'started_at', 'completed_at', 'time_spent_seconds',
            'status', 'quality_score', 'responses',
        ]
        read_only_fields = ['uuid', 'quality_score', 'time_spent_seconds']

    def validate(self, data):
        if data.get('status') == 'completed' and not data.get('completed_at'):
            raise serializers.ValidationError(
                {"completed_at": "completed_at is required when status is 'completed'."}
            )
        return data
