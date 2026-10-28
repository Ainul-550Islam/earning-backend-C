# api/cms/services_new/ProfileSurveyService.py
"""
Service layer for Profile-based Survey System
Handles intelligent survey matching and recommendations
"""
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Sum, Avg

from ..models_new.profile_surveys import (
    SurveyTemplate, SurveyCategory, SurveyCompletion, SurveyResponse
)

logger = logging.getLogger(__name__)
User = get_user_model()


class ProfileSurveyManager:
    """
    Main service for profile-based survey management
    """
    
    def __init__(self):
        self.cache_timeout = 600  # 10 minutes
    
    def get_recommended_surveys(self, user, limit: int = 10) -> List[Dict]:
        """Get personalized survey recommendations"""
        cache_key = f"survey_recommendations_{user.id}"
        
        cached = cache.get(cache_key)
        if cached:
            return cached[:limit]
        
        # Get matching surveys
        surveys = SurveyTemplate.objects.filter(
            status='active'
        ).select_related('category', 'reward_currency')
        
        recommendations = []
        for survey in surveys:
            if survey.matches_user_profile(user):
                score = self._calculate_match_score(survey, user)
                recommendations.append({
                    'survey': survey,
                    'match_score': score,
                    'estimated_reward': float(survey.base_reward + survey.bonus_reward),
                    'estimated_minutes': survey.estimated_minutes,
                    'completion_rate': float(survey.get_completion_rate()),
                })
        
        # Sort by match score
        recommendations.sort(key=lambda x: x['match_score'], reverse=True)
        
        # Cache and return
        cache.set(cache_key, recommendations, self.cache_timeout)
        return recommendations[:limit]
    
    def _calculate_match_score(self, survey: SurveyTemplate, user) -> float:
        """Calculate survey-user match score (0-100)"""
        try:
            profile = user.profile
        except AttributeError:
            return 0.0
        
        score = 0.0
        max_score = 0.0
        
        # Age (20 points)
        if survey.min_age or survey.max_age:
            max_score += 20
            if profile.age and self._age_matches(profile.age, survey):
                score += 20
        
        # Country (15 points)
        if survey.target_countries:
            max_score += 15
            if profile.country and profile.country in survey.target_countries:
                score += 15
        
        # Interests (25 points)
        if survey.target_interests:
            max_score += 25
            user_interests = getattr(profile, 'interests', [])
            matches = len(set(survey.target_interests) & set(user_interests))
            if user_interests:
                score += (matches / len(survey.target_interests)) * 25
        
        # Education (10 points)
        if survey.target_education:
            max_score += 10
            if profile.education and profile.education in survey.target_education:
                score += 10
        
        # Income (10 points)
        if survey.target_income_levels:
            max_score += 10
            if profile.income_level and profile.income_level in survey.target_income_levels:
                score += 10
        
        # Gender (5 points)
        if survey.target_genders:
            max_score += 5
            if profile.gender and profile.gender in survey.target_genders:
                score += 5
        
        # Account age (10 points)
        if survey.min_account_age_days:
            max_score += 10
            account_age = (timezone.now() - user.date_joined).days
            if account_age >= survey.min_account_age_days:
                score += 10
        
        # Experience (5 points)
        if survey.min_completed_surveys:
            max_score += 5
            completed = SurveyCompletion.objects.filter(
                user=user, status='approved'
            ).count()
            if completed >= survey.min_completed_surveys:
                score += 5
        
        return min((score / max_score * 100), 100) if max_score > 0 else 0.0
    
    def _age_matches(self, age: int, survey: SurveyTemplate) -> bool:
        """Check if age matches survey criteria"""
        if survey.min_age and age < survey.min_age:
            return False
        if survey.max_age and age > survey.max_age:
            return False
        return True
    
    def start_survey(self, user, survey_uuid: str) -> Dict[str, Any]:
        """Start a survey for user"""
        try:
            survey = SurveyTemplate.objects.get(uuid=survey_uuid, status='active')
        except SurveyTemplate.DoesNotExist:
            raise ValueError("Survey not found or not active")
        
        # Check if already started
        if SurveyCompletion.objects.filter(survey=survey, user=user).exists():
            raise ValueError("User already started this survey")
        
        # Check if matches profile
        if not survey.matches_user_profile(user):
            raise ValueError("Survey does not match user profile")
        
        # Check daily limit
        if survey.daily_completions_limit:
            today_count = survey.get_daily_completions()
            if today_count >= survey.daily_completions_limit:
                raise ValueError("Daily completion limit reached")
        
        # Create completion
        completion = SurveyCompletion.objects.create(
            survey=survey,
            user=user
        )
        
        return {
            'completion_uuid': str(completion.uuid),
            'survey': {
                'uuid': str(survey.uuid),
                'title': survey.title,
                'description': survey.description,
                'estimated_minutes': survey.estimated_minutes,
                'questions': [
                    {
                        'uuid': str(q.uuid),
                        'text': q.question_text,
                        'type': q.question_type,
                        'required': q.is_required,
                        'choices': q.choices,
                        'help_text': q.help_text
                    }
                    for q in survey.questions.all().order_by('order')
                ]
            }
        }
    
    def submit_survey(self, user, completion_uuid: str, responses: Dict) -> SurveyCompletion:
        """Submit completed survey"""
        try:
            completion = SurveyCompletion.objects.get(
                uuid=completion_uuid, user=user, status='started'
            )
        except SurveyCompletion.DoesNotExist:
            raise ValueError("Survey completion not found or not in started status")
        
        # Validate responses
        self._validate_responses(completion.survey, responses)
        
        # Analyze quality
        quality_score = self._analyze_response_quality(responses, completion.survey)
        
        # Complete survey
        completion.complete_survey(responses, quality_score)
        
        # Clear recommendation cache
        cache.delete(f"survey_recommendations_{user.id}")
        
        return completion
    
    def _validate_responses(self, survey: SurveyTemplate, responses: Dict):
        """Validate survey responses"""
        required_questions = survey.questions.filter(is_required=True)
        
        for question in required_questions:
            if str(question.uuid) not in responses:
                raise ValueError(f"Required question {question.uuid} not answered")
        
        # Validate response formats
        for question in survey.questions.all():
            question_uuid = str(question.uuid)
            if question_uuid in responses:
                answer = responses[question_uuid]
                
                if question.question_type == 'single_choice':
                    if answer not in question.choices:
                        raise ValueError(f"Invalid choice for question {question_uuid}")
                
                elif question.question_type == 'multiple_choice':
                    if not isinstance(answer, list):
                        raise ValueError(f"Multiple choice requires list for question {question_uuid}")
                    if not all(choice in question.choices for choice in answer):
                        raise ValueError(f"Invalid choices for question {question_uuid}")
                
                elif question.question_type == 'number':
                    try:
                        num = Decimal(str(answer))
                        if question.min_value and num < question.min_value:
                            raise ValueError(f"Value below minimum for question {question_uuid}")
                        if question.max_value and num > question.max_value:
                            raise ValueError(f"Value above maximum for question {question_uuid}")
                    except (ValueError, TypeError):
                        raise ValueError(f"Invalid number for question {question_uuid}")
    
    def _analyze_response_quality(self, responses: Dict, survey: SurveyTemplate) -> Decimal:
        """Analyze response quality (0-1)"""
        score = Decimal('1.0')
        
        # Check for straight-lining
        if len(responses) > 1:
            answers = [str(r) for r in responses.values() if isinstance(r, (str, int, float))]
            if len(set(answers)) == 1 and len(answers) > 3:
                score -= Decimal('0.2')
        
        # Check for inconsistent patterns
        # Add more sophisticated quality checks here
        
        return max(score, Decimal('0'))
    
    def get_survey_analytics(self, survey_uuid: str) -> Dict[str, Any]:
        """Get comprehensive survey analytics"""
        try:
            survey = SurveyTemplate.objects.get(uuid=survey_uuid)
        except SurveyTemplate.DoesNotExist:
            return {}
        
        # Basic stats
        stats = SurveyCompletion.objects.filter(survey=survey).aggregate(
            total_started=Count('id'),
            total_completed=Count('id', filter=Q(status='completed')),
            total_approved=Count('id', filter=Q(status='approved')),
            avg_quality=Avg('quality_score'),
            avg_time=Avg('time_spent_seconds')
        )
        
        completion_rate = (stats['total_completed'] / stats['total_started'] * 100) if stats['total_started'] > 0 else 0
        approval_rate = (stats['total_approved'] / stats['total_completed'] * 100) if stats['total_completed'] > 0 else 0
        
        # Demographics
        demographics = self._get_survey_demographics(survey)
        
        return {
            'survey_uuid': str(survey.uuid),
            'title': survey.title,
            'category': survey.category.name,
            'total_started': stats['total_started'],
            'total_completed': stats['total_completed'],
            'total_approved': stats['total_approved'],
            'completion_rate': round(completion_rate, 2),
            'approval_rate': round(approval_rate, 2),
            'avg_quality_score': round(float(stats['avg_quality'] or 0), 2),
            'avg_time_seconds': round(float(stats['avg_time'] or 0), 2),
            'total_payout': float(stats['total_approved'] * survey.base_reward),
            'demographics': demographics,
        }
    
    def _get_survey_demographics(self, survey: SurveyTemplate) -> Dict[str, Any]:
        """Get demographic breakdown for survey"""
        completions = SurveyCompletion.objects.filter(
            survey=survey, status='approved'
        ).select_related('user__profile')
        
        demographics = {
            'age_groups': {},
            'genders': {},
            'countries': {},
            'education_levels': {}
        }
        
        for completion in completions:
            profile = completion.user.profile
            
            # Age groups
            if profile.age:
                age_group = self._get_age_group(profile.age)
                demographics['age_groups'][age_group] = demographics['age_groups'].get(age_group, 0) + 1
            
            # Gender
            if profile.gender:
                demographics['genders'][profile.gender] = demographics['genders'].get(profile.gender, 0) + 1
            
            # Country
            if profile.country:
                demographics['countries'][profile.country] = demographics['countries'].get(profile.country, 0) + 1
            
            # Education
            if profile.education:
                demographics['education_levels'][profile.education] = demographics['education_levels'].get(profile.education, 0) + 1
        
        return demographics
    
    def _get_age_group(self, age: int) -> str:
        """Get age group category"""
        if age < 18:
            return 'Under 18'
        elif age < 25:
            return '18-24'
        elif age < 35:
            return '25-34'
        elif age < 45:
            return '35-44'
        elif age < 55:
            return '45-54'
        else:
            return '55+'
    
    def get_user_survey_history(self, user, limit: int = 50) -> List[Dict]:
        """Get user's survey completion history"""
        completions = SurveyCompletion.objects.filter(
            user=user
        ).select_related('survey').order_by('-started_at')[:limit]
        
        history = []
        for completion in completions:
            history.append({
                'uuid': str(completion.uuid),
                'survey_title': completion.survey.title,
                'category': completion.survey.category.name,
                'status': completion.get_status_display(),
                'started_at': completion.started_at.isoformat(),
                'completed_at': completion.completed_at.isoformat() if completion.completed_at else None,
                'time_spent_seconds': completion.time_spent_seconds,
                'total_reward': float(completion.total_reward_earned),
                'quality_score': float(completion.quality_score) if completion.quality_score else None,
            })
        
        return history
