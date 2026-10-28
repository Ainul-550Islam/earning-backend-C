# api/cms/serializers_new/QuizSerializer.py
"""
Serializers for Quiz Models
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models_new.quiz import QuizTemplate, QuizQuestion, QuizAnswer, QuizResult, QuizAttempt

User = get_user_model()


class QuizAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizAnswer
        fields = ['id', 'question', 'text', 'personality_tag', 'score_weight', 'image_url', 'order']
        read_only_fields = ['id']


class QuizQuestionSerializer(serializers.ModelSerializer):
    answers = QuizAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = QuizQuestion
        fields = ['id', 'quiz', 'text', 'question_type', 'order', 'is_required', 'image_url', 'answers']
        read_only_fields = ['id']


class QuizResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizResult
        fields = [
            'id', 'quiz', 'title', 'description', 'image_url',
            'personality_tag', 'share_text', 'min_score', 'max_score',
        ]
        read_only_fields = ['id']


class QuizTemplateSerializer(serializers.ModelSerializer):
    questions = QuizQuestionSerializer(many=True, read_only=True)
    results = QuizResultSerializer(many=True, read_only=True)

    class Meta:
        model = QuizTemplate
        fields = [
            'uuid', 'title', 'slug', 'description', 'quiz_type', 'thumbnail',
            'cpalead_offer_id', 'payout_usd', 'questions', 'results',
        ]
        read_only_fields = ['uuid']


class QuizAttemptSerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source='user', read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            'uuid', 'quiz', 'user', 'user_display', 'session_key',
            'result', 'answers_data', 'total_score', 'is_completed',
        ]
        read_only_fields = ['uuid', 'total_score']

    def validate(self, data):
        if data.get('is_completed') and not data.get('result'):
            raise serializers.ValidationError(
                {"result": "A completed attempt must have a result."}
            )
        return data
