# api/cms/viewsets_new/ProfileSurveyViewSet.py
"""
API ViewSets for Profile-based Survey System
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from decimal import Decimal

from ..models_new.profile_surveys import (
    SurveyCategory, SurveyTemplate, SurveyQuestion, SurveyCompletion, SurveyResponse
)
from ..services_new.ProfileSurveyService import ProfileSurveyManager


class SurveyCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for survey categories
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active']
    
    def get_queryset(self):
        return SurveyCategory.objects.filter(is_active=True).order_by('order', 'name')


class SurveyTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for survey templates
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'survey_type', 'status']
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return SurveyTemplate.objects.all().select_related('category', 'reward_currency')
        return SurveyTemplate.objects.filter(
            status='active'
        ).select_related('category', 'reward_currency')
    
    def perform_create(self, serializer):
        if not self.request.user.is_staff:
            raise PermissionError("Only staff can create surveys")
        serializer.save()
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start a survey for current user"""
        try:
            result = ProfileSurveyManager().start_survey(request.user, pk)
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit completed survey"""
        completion_uuid = request.data.get('completion_uuid')
        responses = request.data.get('responses', {})
        
        if not completion_uuid:
            return Response({'error': 'completion_uuid required'}, status=400)
        
        try:
            completion = ProfileSurveyManager().submit_survey(
                request.user, completion_uuid, responses
            )
            return Response({
                'completion_uuid': str(completion.uuid),
                'status': completion.get_status_display(),
                'total_reward': float(completion.total_reward_earned),
                'quality_score': float(completion.quality_score) if completion.quality_score else None
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=True, methods=['get'])
    def questions(self, request, pk=None):
        """Get survey questions"""
        try:
            survey = SurveyTemplate.objects.get(uuid=pk, status='active')
            questions = survey.questions.all().order_by('order')
            data = []
            for question in questions:
                data.append({
                    'uuid': str(question.uuid),
                    'text': question.question_text,
                    'type': question.question_type,
                    'required': question.is_required,
                    'choices': question.choices,
                    'help_text': question.help_text,
                    'min_value': float(question.min_value) if question.min_value else None,
                    'max_value': float(question.max_value) if question.max_value else None,
                    'order': question.order
                })
            return Response(data)
        except SurveyTemplate.DoesNotExist:
            return Response({'error': 'Survey not found'}, status=404)
    
    @action(detail=False, methods=['get'])
    def recommended(self, request):
        """Get personalized survey recommendations"""
        limit = min(int(request.query_params.get('limit', 10)), 50)
        
        try:
            recommendations = ProfileSurveyManager().get_recommended_surveys(request.user, limit)
            data = []
            for rec in recommendations:
                survey = rec['survey']
                data.append({
                    'uuid': str(survey.uuid),
                    'title': survey.title,
                    'description': survey.description,
                    'category': survey.category.name,
                    'survey_type': survey.survey_type,
                    'estimated_minutes': survey.estimated_minutes,
                    'estimated_reward': rec['estimated_reward'],
                    'match_score': rec['match_score'],
                    'completion_rate': rec['completion_rate']
                })
            return Response(data)
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        """Get user's survey completion history"""
        limit = min(int(request.query_params.get('limit', 50)), 100)
        
        try:
            history = ProfileSurveyManager().get_user_survey_history(request.user, limit)
            return Response(history)
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get survey analytics (admin only)"""
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        try:
            analytics = ProfileSurveyManager().get_survey_analytics(pk)
            return Response(analytics)
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=True, methods=['post'])
    def create_survey(self, request):
        """Create a new survey (admin only)"""
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        try:
            # This would need a serializer for SurveyTemplate creation
            # For now, return a placeholder response
            return Response({'message': 'Survey creation endpoint - implement serializer'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class SurveyQuestionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for survey questions
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return SurveyQuestion.objects.all().select_related('survey', 'depends_on')
        return SurveyQuestion.objects.filter(
            survey__status='active'
        ).select_related('survey', 'depends_on')


class SurveyCompletionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for survey completions
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return SurveyCompletion.objects.all().select_related('survey', 'user')
        return SurveyCompletion.objects.filter(
            user=self.request.user
        ).select_related('survey')
    
    @action(detail=False, methods=['get'])
    def my_completions(self, request):
        """Get current user's completions"""
        completions = self.get_queryset().filter(user=request.user)
        data = []
        for completion in completions:
            data.append({
                'uuid': str(completion.uuid),
                'survey_title': completion.survey.title,
                'status': completion.get_status_display(),
                'started_at': completion.started_at.isoformat(),
                'completed_at': completion.completed_at.isoformat() if completion.completed_at else None,
                'time_spent_seconds': completion.time_spent_seconds,
                'total_reward': float(completion.total_reward_earned),
                'quality_score': float(completion.quality_score) if completion.quality_score else None
            })
        return Response(data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get completion statistics (admin only)"""
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        # Get overall statistics
        stats = SurveyCompletion.objects.aggregate(
            total_started=Count('id'),
            total_completed=Count('id', filter=Q(status='completed')),
            total_approved=Count('id', filter=Q(status='approved')),
            avg_quality=Avg('quality_score'),
            total_payout=Sum('total_reward_earned')
        )
        
        completion_rate = (stats['total_completed'] / stats['total_started'] * 100) if stats['total_started'] > 0 else 0
        approval_rate = (stats['total_approved'] / stats['total_completed'] * 100) if stats['total_completed'] > 0 else 0
        
        return Response({
            'total_started': stats['total_started'],
            'total_completed': stats['total_completed'],
            'total_approved': stats['total_approved'],
            'completion_rate': round(completion_rate, 2),
            'approval_rate': round(approval_rate, 2),
            'avg_quality_score': round(float(stats['avg_quality'] or 0), 2),
            'total_payout': float(stats['total_payout'] or 0)
        })


class SurveyResponseViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for survey responses (admin only)
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if not self.request.user.is_staff:
            return SurveyResponse.objects.none()
        return SurveyResponse.objects.all().select_related('completion', 'question', 'completion__user')
    
    @action(detail=False, methods=['get'])
    def completion_responses(self, request):
        """Get responses for a specific completion"""
        completion_uuid = request.query_params.get('completion_uuid')
        
        if not completion_uuid:
            return Response({'error': 'completion_uuid required'}, status=400)
        
        try:
            completion = SurveyCompletion.objects.get(uuid=completion_uuid)
            responses = completion.responses.all().select_related('question')
            data = []
            for response in responses:
                data.append({
                    'uuid': str(response.uuid),
                    'question_text': response.question.question_text,
                    'question_type': response.question.question_type,
                    'answer': response.answer,
                    'answer_text': response.answer_text,
                    'answer_number': float(response.answer_number) if response.answer_number else None,
                    'response_time_seconds': response.response_time_seconds,
                    'is_attention_check': response.is_attention_check
                })
            return Response(data)
        except SurveyCompletion.DoesNotExist:
            return Response({'error': 'Completion not found'}, status=404)
