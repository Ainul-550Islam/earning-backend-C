# api/cms/services_new/SurveyAnalyticsService.py
"""
Advanced Analytics Service for Survey System
Provides comprehensive analytics and reporting capabilities
"""
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg, StdDev, Min, Max, F, Window
from django.db.models.functions import TruncDate, TruncHour, Extract
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator

from ..models_new.profile_surveys import (
    SurveyTemplate, SurveyCompletion, SurveyResponse, SurveyCategory
)
from ..models_new.survey_rewards import RewardTransaction, SurveyReward
from ..models_new.user_profile import UserProfile, UserSegment

logger = logging.getLogger(__name__)
User = get_user_model()


class SurveyAnalyticsService:
    """
    Comprehensive analytics service for survey data
    """
    
    def __init__(self):
        self.cache_timeout = 1800  # 30 minutes
    
    def get_dashboard_overview(self, days: int = 30) -> Dict[str, Any]:
        """Get dashboard overview statistics"""
        cache_key = f"survey_dashboard_overview_{days}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        start_date = timezone.now() - timedelta(days=days)
        
        # Basic metrics
        total_surveys = SurveyTemplate.objects.filter(status='active').count()
        total_completions = SurveyCompletion.objects.filter(
            started_at__gte=start_date
        ).count()
        total_approved = SurveyCompletion.objects.filter(
            started_at__gte=start_date, status='approved'
        ).count()
        
        # User metrics
        active_users = User.objects.filter(
            survey_completions__started_at__gte=start_date
        ).distinct().count()
        
        # Revenue metrics
        total_payout = SurveyCompletion.objects.filter(
            started_at__gte=start_date, status='approved'
        ).aggregate(total=Sum('total_reward_earned'))['total'] or Decimal('0')
        
        # Quality metrics
        avg_quality = SurveyCompletion.objects.filter(
            started_at__gte=start_date, status='approved'
        ).aggregate(avg=Avg('quality_score'))['avg'] or 0
        
        # Completion rates
        completion_rate = (total_approved / total_completions * 100) if total_completions > 0 else 0
        
        # Daily trends
        daily_stats = self._get_daily_trends(start_date)
        
        # Top performing surveys
        top_surveys = self._get_top_performing_surveys(start_date, limit=5)
        
        # Demographic breakdown
        demographics = self._get_demographic_breakdown(start_date)
        
        overview = {
            'period_days': days,
            'total_surveys': total_surveys,
            'total_completions': total_completions,
            'total_approved': total_approved,
            'active_users': active_users,
            'total_payout': float(total_payout),
            'avg_quality_score': round(float(avg_quality), 2),
            'completion_rate': round(completion_rate, 2),
            'daily_trends': daily_stats,
            'top_surveys': top_surveys,
            'demographics': demographics,
            'generated_at': timezone.now().isoformat()
        }
        
        cache.set(cache_key, overview, self.cache_timeout)
        return overview
    
    def get_survey_performance_report(self, survey_uuid: str, days: int = 30) -> Dict[str, Any]:
        """Get detailed performance report for a specific survey"""
        cache_key = f"survey_performance_{survey_uuid}_{days}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        try:
            survey = SurveyTemplate.objects.get(uuid=survey_uuid)
        except SurveyTemplate.DoesNotExist:
            return {}
        
        start_date = timezone.now() - timedelta(days=days)
        
        # Basic stats
        completions = SurveyCompletion.objects.filter(
            survey=survey, started_at__gte=start_date
        )
        
        total_started = completions.count()
        total_completed = completions.filter(status='completed').count()
        total_approved = completions.filter(status='approved').count()
        
        # Time analytics
        time_stats = completions.filter(status='approved').aggregate(
            avg_time=Avg('time_spent_seconds'),
            min_time=Min('time_spent_seconds'),
            max_time=Max('time_spent_seconds'),
            std_dev=StdDev('time_spent_seconds')
        )
        
        # Quality analytics
        quality_stats = completions.filter(status='approved').aggregate(
            avg_quality=Avg('quality_score'),
            min_quality=Min('quality_score'),
            max_quality=Max('quality_score')
        )
        
        # Drop-off analysis
        drop_off = self._analyze_drop_off_points(survey)
        
        # Response analysis
        response_analysis = self._analyze_question_responses(survey)
        
        # Demographic analysis
        demographic_analysis = self._get_survey_demographic_analysis(survey, start_date)
        
        # Financial analysis
        financial_analysis = self._get_survey_financial_analysis(survey, start_date)
        
        # Time series data
        time_series = self._get_survey_time_series(survey, start_date)
        
        report = {
            'survey_uuid': str(survey.uuid),
            'survey_title': survey.title,
            'survey_category': survey.category.name,
            'period_days': days,
            'basic_stats': {
                'total_started': total_started,
                'total_completed': total_completed,
                'total_approved': total_approved,
                'completion_rate': round((total_completed / total_started * 100) if total_started > 0 else 0, 2),
                'approval_rate': round((total_approved / total_completed * 100) if total_completed > 0 else 0, 2)
            },
            'time_analytics': {
                'avg_time_seconds': round(float(time_stats['avg_time'] or 0), 2),
                'min_time_seconds': time_stats['min_time'] or 0,
                'max_time_seconds': time_stats['max_time'] or 0,
                'std_dev_seconds': round(float(time_stats['std_dev'] or 0), 2)
            },
            'quality_analytics': {
                'avg_quality_score': round(float(quality_stats['avg_quality'] or 0), 2),
                'min_quality_score': float(quality_stats['min_quality'] or 0),
                'max_quality_score': float(quality_stats['max_quality'] or 0)
            },
            'drop_off_analysis': drop_off,
            'response_analysis': response_analysis,
            'demographic_analysis': demographic_analysis,
            'financial_analysis': financial_analysis,
            'time_series': time_series,
            'generated_at': timezone.now().isoformat()
        }
        
        cache.set(cache_key, report, self.cache_timeout)
        return report
    
    def get_user_analytics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get analytics for a specific user"""
        cache_key = f"user_analytics_{user_id}_{days}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        try:
            user = User.objects.get(id=user_id)
            profile = user.profile
        except (User.DoesNotExist, AttributeError):
            return {}
        
        start_date = timezone.now() - timedelta(days=days)
        
        # Survey participation
        completions = SurveyCompletion.objects.filter(
            user=user, started_at__gte=start_date
        )
        
        total_started = completions.count()
        total_completed = completions.filter(status='completed').count()
        total_approved = completions.filter(status='approved').count()
        
        # Earnings
        total_earnings = completions.filter(status='approved').aggregate(
            total=Sum('total_reward_earned')
        )['total'] or Decimal('0')
        
        # Performance metrics
        avg_quality = completions.filter(status='approved').aggregate(
            avg=Avg('quality_score')
        )['avg'] or 0
        
        avg_completion_time = completions.filter(status='approved').aggregate(
            avg=Avg('time_spent_seconds')
        )['avg'] or 0
        
        # Category preferences
        category_stats = completions.filter(status='approved').values(
            'survey__category__name'
        ).annotate(
            count=Count('id'),
            total_earnings=Sum('total_reward_earned')
        ).order_by('-count')
        
        # Time series activity
        activity_series = self._get_user_activity_series(user, start_date)
        
        # Quality trends
        quality_trends = self._get_user_quality_trends(user, start_date)
        
        analytics = {
            'user_id': user_id,
            'username': user.username,
            'profile_completeness': float(profile.profile_completeness) if profile else 0,
            'period_days': days,
            'participation_stats': {
                'total_started': total_started,
                'total_completed': total_completed,
                'total_approved': total_approved,
                'completion_rate': round((total_completed / total_started * 100) if total_started > 0 else 0, 2),
                'approval_rate': round((total_approved / total_completed * 100) if total_completed > 0 else 0, 2)
            },
            'earnings': {
                'total_earnings': float(total_earnings),
                'avg_per_survey': float(total_earnings / total_approved) if total_approved > 0 else 0
            },
            'performance_metrics': {
                'avg_quality_score': round(float(avg_quality), 2),
                'avg_completion_time_seconds': round(float(avg_completion_time), 2)
            },
            'category_preferences': list(category_stats),
            'activity_series': activity_series,
            'quality_trends': quality_trends,
            'generated_at': timezone.now().isoformat()
        }
        
        cache.set(cache_key, analytics, self.cache_timeout)
        return analytics
    
    def get_real_time_metrics(self) -> Dict[str, Any]:
        """Get real-time survey metrics"""
        cache_key = "survey_real_time_metrics"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        now = timezone.now()
        last_hour = now - timedelta(hours=1)
        last_24h = now - timedelta(hours=24)
        
        # Active surveys right now
        active_surveys = SurveyTemplate.objects.filter(
            status='active',
            start_time__lte=now,
            end_time__gte=now
        ).count()
        
        # Completions in last hour
        completions_last_hour = SurveyCompletion.objects.filter(
            started_at__gte=last_hour
        ).count()
        
        # Completions in last 24h
        completions_last_24h = SurveyCompletion.objects.filter(
            started_at__gte=last_24h
        ).count()
        
        # Currently active users (started survey in last 30 minutes)
        active_users = SurveyCompletion.objects.filter(
            started_at__gte=now - timedelta(minutes=30),
            status='in_progress'
        ).values('user').distinct().count()
        
        # Recent quality scores
        recent_quality = SurveyCompletion.objects.filter(
            started_at__gte=last_hour,
            status='approved'
        ).aggregate(avg=Avg('quality_score'))['avg'] or 0
        
        metrics = {
            'timestamp': now.isoformat(),
            'active_surveys': active_surveys,
            'completions_last_hour': completions_last_hour,
            'completions_last_24h': completions_last_24h,
            'active_users': active_users,
            'recent_avg_quality': round(float(recent_quality), 2),
            'completion_rate_per_hour': round(completions_last_hour, 2)
        }
        
        cache.set(cache_key, metrics, 300)  # 5 minutes cache
        return metrics
    
    def _get_daily_trends(self, start_date: datetime) -> List[Dict]:
        """Get daily completion trends"""
        return list(
            SurveyCompletion.objects.filter(
                started_at__gte=start_date
            ).annotate(
                date=TruncDate('started_at')
            ).values('date').annotate(
                started=Count('id'),
                completed=Count('id', filter=Q(status='completed')),
                approved=Count('id', filter=Q(status='approved'))
            ).order_by('date')
        )
    
    def _get_top_performing_surveys(self, start_date: datetime, limit: int = 5) -> List[Dict]:
        """Get top performing surveys by completion count"""
        return list(
            SurveyCompletion.objects.filter(
                started_at__gte=start_date,
                status='approved'
            ).values(
                'survey__uuid', 'survey__title', 'survey__category__name'
            ).annotate(
                completions=Count('id'),
                total_payout=Sum('total_reward_earned'),
                avg_quality=Avg('quality_score')
            ).order_by('-completions')[:limit]
        )
    
    def _get_demographic_breakdown(self, start_date: datetime) -> Dict[str, Any]:
        """Get demographic breakdown of survey participants"""
        completions = SurveyCompletion.objects.filter(
            started_at__gte=start_date,
            status='approved'
        ).select_related('user__profile')
        
        breakdown = {
            'age_groups': {},
            'genders': {},
            'countries': {},
            'education_levels': {}
        }
        
        for completion in completions:
            profile = completion.user.profile
            if not profile:
                continue
            
            # Age groups
            if profile.age:
                age_group = self._get_age_group(profile.age)
                breakdown['age_groups'][age_group] = breakdown['age_groups'].get(age_group, 0) + 1
            
            # Gender
            if profile.gender:
                breakdown['genders'][profile.gender] = breakdown['genders'].get(profile.gender, 0) + 1
            
            # Country
            if profile.country:
                breakdown['countries'][profile.country] = breakdown['countries'].get(profile.country, 0) + 1
            
            # Education
            if profile.education:
                breakdown['education_levels'][profile.education] = breakdown['education_levels'].get(profile.education, 0) + 1
        
        return breakdown
    
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
    
    def _analyze_drop_off_points(self, survey: SurveyTemplate) -> List[Dict]:
        """Analyze where users drop off during survey"""
        questions = list(survey.questions.all().order_by('order'))
        drop_off_points = []
        
        for i, question in enumerate(questions):
            # Count responses up to this question
            responses_up_to = SurveyResponse.objects.filter(
                completion__survey=survey,
                question__order__lte=question.order
            ).values('completion').distinct().count()
            
            # Count total completions
            total_completions = SurveyCompletion.objects.filter(survey=survey).count()
            
            if total_completions > 0:
                drop_off_rate = ((total_completions - responses_up_to) / total_completions) * 100
                drop_off_points.append({
                    'question_order': question.order,
                    'question_text': question.question_text[:100],
                    'drop_off_rate': round(drop_off_rate, 2),
                    'responses_up_to': responses_up_to,
                    'total_completions': total_completions
                })
        
        return drop_off_points
    
    def _analyze_question_responses(self, survey: SurveyTemplate) -> List[Dict]:
        """Analyze response patterns for survey questions"""
        questions = survey.questions.all()
        analysis = []
        
        for question in questions:
            responses = SurveyResponse.objects.filter(
                question=question,
                completion__status='approved'
            )
            
            question_analysis = {
                'question_uuid': str(question.uuid),
                'question_text': question.question_text[:100],
                'question_type': question.question_type,
                'total_responses': responses.count(),
                'response_patterns': {}
            }
            
            if question.question_type in ['single_choice', 'multiple_choice']:
                # Analyze choice distribution
                choice_counts = {}
                for response in responses:
                    answer = response.answer
                    if isinstance(answer, list):
                        for choice in answer:
                            choice_counts[choice] = choice_counts.get(choice, 0) + 1
                    else:
                        choice_counts[answer] = choice_counts.get(answer, 0) + 1
                
                question_analysis['response_patterns']['choice_distribution'] = choice_counts
            
            elif question.question_type == 'number':
                # Analyze numeric responses
                numeric_stats = responses.aggregate(
                    avg=Avg('answer_number'),
                    min=Min('answer_number'),
                    max=Max('answer_number'),
                    std_dev=StdDev('answer_number')
                )
                question_analysis['response_patterns']['numeric_stats'] = {
                    'avg': round(float(numeric_stats['avg'] or 0), 2),
                    'min': float(numeric_stats['min'] or 0),
                    'max': float(numeric_stats['max'] or 0),
                    'std_dev': round(float(numeric_stats['std_dev'] or 0), 2)
                }
            
            elif question.question_type == 'text':
                # Analyze text responses (length distribution)
                text_lengths = [len(r.answer_text or '') for r in responses]
                if text_lengths:
                    question_analysis['response_patterns']['text_stats'] = {
                        'avg_length': round(sum(text_lengths) / len(text_lengths), 2),
                        'min_length': min(text_lengths),
                        'max_length': max(text_lengths)
                    }
            
            analysis.append(question_analysis)
        
        return analysis
    
    def _get_survey_demographic_analysis(self, survey: SurveyTemplate, start_date: datetime) -> Dict[str, Any]:
        """Get demographic analysis for a specific survey"""
        completions = SurveyCompletion.objects.filter(
            survey=survey,
            started_at__gte=start_date,
            status='approved'
        ).select_related('user__profile')
        
        return self._get_demographic_breakdown(start_date)  # Reuse existing method
    
    def _get_survey_financial_analysis(self, survey: SurveyTemplate, start_date: datetime) -> Dict[str, Any]:
        """Get financial analysis for a specific survey"""
        completions = SurveyCompletion.objects.filter(
            survey=survey,
            started_at__gte=start_date,
            status='approved'
        )
        
        financial_stats = completions.aggregate(
            total_payout=Sum('total_reward_earned'),
            avg_payout=Avg('total_reward_earned'),
            min_payout=Min('total_reward_earned'),
            max_payout=Max('total_reward_earned')
        )
        
        return {
            'total_payout': float(financial_stats['total_payout'] or 0),
            'avg_payout': round(float(financial_stats['avg_payout'] or 0), 2),
            'min_payout': float(financial_stats['min_payout'] or 0),
            'max_payout': float(financial_stats['max_payout'] or 0),
            'total_completions': completions.count()
        }
    
    def _get_survey_time_series(self, survey: SurveyTemplate, start_date: datetime) -> List[Dict]:
        """Get time series data for survey completions"""
        return list(
            SurveyCompletion.objects.filter(
                survey=survey,
                started_at__gte=start_date
            ).annotate(
                date=TruncDate('started_at')
            ).values('date').annotate(
                started=Count('id'),
                completed=Count('id', filter=Q(status='completed')),
                approved=Count('id', filter=Q(status='approved')),
                total_payout=Sum('total_reward_earned', filter=Q(status='approved'))
            ).order_by('date')
        )
    
    def _get_user_activity_series(self, user: User, start_date: datetime) -> List[Dict]:
        """Get user activity time series"""
        return list(
            SurveyCompletion.objects.filter(
                user=user,
                started_at__gte=start_date
            ).annotate(
                date=TruncDate('started_at')
            ).values('date').annotate(
                started=Count('id'),
                completed=Count('id', filter=Q(status='completed')),
                approved=Count('id', filter=Q(status='approved')),
                total_earnings=Sum('total_reward_earned', filter=Q(status='approved'))
            ).order_by('date')
        )
    
    def _get_user_quality_trends(self, user: User, start_date: datetime) -> List[Dict]:
        """Get user quality score trends"""
        return list(
            SurveyCompletion.objects.filter(
                user=user,
                started_at__gte=start_date,
                status='approved'
            ).annotate(
                date=TruncDate('started_at')
            ).values('date').annotate(
                avg_quality=Avg('quality_score'),
                count=Count('id')
            ).order_by('date')
        )
