# api/cms/models_new/profile_surveys.py
"""
Profile-based Survey System
Intelligent survey matching based on user demographics and preferences
"""
import uuid
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import models
from django.db.models import Q, F, Count, Sum, Avg
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.db.models.functions import Cast

logger = logging.getLogger(__name__)
User = get_user_model()


class SurveyCategory(models.Model):
    """
    Survey categories for classification
    """
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(_("Name"), max_length=100)
    slug = models.SlugField(_("Slug"), unique=True, max_length=100)
    description = models.TextField(_("Description"), blank=True)
    icon = models.CharField(_("Icon"), max_length=50, blank=True)
    
    # Targeting criteria
    min_age = models.PositiveIntegerField(_("Min Age"), null=True, blank=True)
    max_age = models.PositiveIntegerField(_("Max Age"), null=True, blank=True)
    target_genders = models.JSONField(_("Target Genders"), default=list, blank=True)
    target_countries = models.JSONField(_("Target Countries"), default=list, blank=True)
    target_income_levels = models.JSONField(_("Target Income Levels"), default=list, blank=True)
    target_education = models.JSONField(_("Target Education"), default=list, blank=True)
    
    is_active = models.BooleanField(_("Active"), default=True)
    order = models.IntegerField(_("Order"), default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = "cms"
        verbose_name = _("Survey Category")
        verbose_name_plural = _("Survey Categories")
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['is_active', 'order']),
            models.Index(fields=['slug']),
        ]
    
    def __str__(self):
        return self.name


class SurveyTemplate(models.Model):
    """
    Survey templates with profile-based targeting
    """
    SURVEY_TYPES = [
        ('profile', _('Profile Survey')),
        ('market_research', _('Market Research')),
        ('product_feedback', _('Product Feedback')),
        ('satisfaction', _('Satisfaction Survey')),
        ('lifestyle', _('Lifestyle Survey')),
        ('interest', _('Interest Survey')),
    ]
    
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('active', _('Active')),
        ('paused', _('Paused')),
        ('completed', _('Completed')),
        ('expired', _('Expired')),
    ]
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(_("Title"), max_length=200)
    description = models.TextField(_("Description"))
    category = models.ForeignKey(SurveyCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='surveys')
    survey_type = models.CharField(_("Survey Type"), max_length=20, choices=SURVEY_TYPES)
    status = models.CharField(_("Status"), max_length=20, choices=STATUS_CHOICES, default='draft')
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active     = models.BooleanField(default=True)
    
    # Targeting criteria
    min_age = models.PositiveIntegerField(_("Min Age"), null=True, blank=True)
    max_age = models.PositiveIntegerField(_("Max Age"), null=True, blank=True)
    target_genders = models.JSONField(_("Target Genders"), default=list, blank=True)
    target_countries = models.JSONField(_("Target Countries"), default=list, blank=True)
    target_income_levels = models.JSONField(_("Target Income Levels"), default=list, blank=True)
    target_education = models.JSONField(_("Target Education"), default=list, blank=True)
    target_interests = models.JSONField(_("Target Interests"), default=list, blank=True)
    target_languages = models.JSONField(_("Target Languages"), default=list, blank=True)
    
    # Device and platform targeting
    target_devices = models.JSONField(_("Target Devices"), default=list, blank=True)
    target_browsers = models.JSONField(_("Target Browsers"), default=list, blank=True)
    target_os = models.JSONField(_("Target Operating Systems"), default=list, blank=True)
    
    # Behavioral targeting
    min_completed_surveys = models.PositiveIntegerField(
        _("Min Completed Surveys"), null=True, blank=True,
        help_text=_("Minimum surveys user must have completed")
    )
    max_completed_surveys = models.PositiveIntegerField(
        _("Max Completed Surveys"), null=True, blank=True,
        help_text=_("Maximum surveys user can have completed")
    )
    min_account_age_days = models.PositiveIntegerField(
        _("Min Account Age (days)"), null=True, blank=True
    )
    target_user_segments = models.JSONField(
        _("Target User Segments"), default=list, blank=True
    )
    
    # Survey configuration
    estimated_minutes = models.PositiveIntegerField(
        _("Estimated Minutes"), default=10,
        help_text=_("Estimated completion time")
    )
    max_completions = models.PositiveIntegerField(
        _("Max Completions"), null=True, blank=True,
        help_text=_("Maximum total completions allowed")
    )
    daily_completions_limit = models.PositiveIntegerField(
        _("Daily Completions Limit"), null=True, blank=True
    )
    
    # Rewards
    base_reward = models.DecimalField(
        _("Base Reward"), max_digits=10, decimal_places=2, default=1.00
    )
    bonus_reward = models.DecimalField(
        _("Bonus Reward"), max_digits=10, decimal_places=2, default=0.00
    )
    reward_currency = models.ForeignKey(
        'cms.VirtualCurrency', on_delete=models.SET_NULL, null=True, blank=True
    )
    
    # Quality control
    enable_attention_checks = models.BooleanField(_("Enable Attention Checks"), default=True)
    enable_speeding_detection = models.BooleanField(_("Enable Speeding Detection"), default=True)
    min_time_seconds = models.PositiveIntegerField(
        _("Min Time (seconds)"), null=True, blank=True
    )
    max_time_seconds = models.PositiveIntegerField(
        _("Max Time (seconds)"), null=True, blank=True
    )
    
    # Timing
    start_time = models.DateTimeField(_("Start Time"), null=True, blank=True)
    end_time = models.DateTimeField(_("End Time"), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = "cms"
        verbose_name = _("Survey Template")
        verbose_name_plural = _("Survey Templates")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'start_time']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['survey_type', 'status']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
    
    def is_active_for_user(self, user) -> bool:
        """Check if survey is active and suitable for user"""
        if self.status != 'active':
            return False
        
        now = timezone.now()
        if self.start_time and now < self.start_time:
            return False
        if self.end_time and now > self.end_time:
            return False
        
        return self.matches_user_profile(user)
    
    def matches_user_profile(self, user) -> bool:
        """Check if user matches survey targeting criteria"""
        try:
            profile = user.profile
        except Exception:
            return False

        # Age matching — skip when profile has no date_of_birth (unknown age = allow)
        if self.min_age or self.max_age:
            age = profile.age  # returns None when no dob
            if age is not None:
                if self.min_age and age < self.min_age:
                    return False
                if self.max_age and age > self.max_age:
                    return False
            # else: age unknown → do not exclude

        # Gender matching — skip if profile has no gender set
        if self.target_genders and profile.gender:
            if profile.gender not in self.target_genders:
                return False

        # Country matching — skip check if user profile has no country set
        if self.target_countries and profile.country:
            if profile.country not in self.target_countries:
                return False

        # Income level matching
        if self.target_income_levels:
            if not profile.income_level or profile.income_level not in self.target_income_levels:
                return False

        # Education matching
        if self.target_education:
            if not profile.education or profile.education not in self.target_education:
                return False

        # Interest matching — skip if user has no interests configured
        if self.target_interests:
            user_interests = getattr(profile, 'interests', []) or []
            if user_interests and not any(interest in user_interests for interest in self.target_interests):
                return False

        return True
    
    def get_completion_rate(self) -> Decimal:
        """Get overall completion rate for this survey, rounded to 2 decimal places."""
        total     = SurveyCompletion.objects.filter(survey=self).count()
        completed = SurveyCompletion.objects.filter(survey=self, status='approved').count()
        if total == 0:
            return Decimal('0')
        return Decimal(str(round(completed / total * 100, 2)))
    
    def get_daily_completions(self) -> int:
        """Get today's completion count"""
        today = timezone.now().date()
        return SurveyCompletion.objects.filter(
            survey=self,
            status='approved',
            completed_at__date=today
        ).count()


class SurveyQuestion(models.Model):
    """
    Individual survey questions
    """
    QUESTION_TYPES = [
        ('single_choice', _('Single Choice')),
        ('multiple_choice', _('Multiple Choice')),
        ('text', _('Text')),
        ('number', _('Number')),
        ('rating', _('Rating Scale')),
        ('matrix', _('Matrix/Grid')),
        ('ranking', _('Ranking')),
        ('date', _('Date')),
        ('file_upload', _('File Upload')),
    ]
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    survey = models.ForeignKey(SurveyTemplate, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField(_("Question Text"))
    question_type = models.CharField(_("Question Type"), max_length=20, choices=QUESTION_TYPES)
    help_text = models.TextField(_("Help Text"), blank=True)
    
    # Configuration
    is_required = models.BooleanField(_("Required"), default=True)
    order = models.IntegerField(_("Order"), default=0)
    
    # Options for choice questions
    choices = models.JSONField(_("Choices"), default=list, blank=True)
    min_value = models.DecimalField(_("Min Value"), max_digits=10, decimal_places=2, null=True, blank=True)
    max_value = models.DecimalField(_("Max Value"), max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Conditional logic
    depends_on = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='dependent_questions'
    )
    show_when_answer = models.JSONField(_("Show When Answer"), default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = "cms"
        verbose_name = _("Survey Question")
        verbose_name_plural = _("Survey Questions")
        ordering = ['order']
        indexes = [
            models.Index(fields=['survey', 'order']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.survey.title} - Q{self.order + 1}"


class SurveyCompletion(models.Model):
    """
    Track survey completions and responses
    """
    STATUS_CHOICES = [
        ('started', _('Started')),
        ('in_progress', _('In Progress')),
        ('completed', _('Completed')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('expired', _('Expired')),
    ]
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    survey = models.ForeignKey(SurveyTemplate, on_delete=models.CASCADE, related_name='completions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='survey_completions')
    
    # Timing
    started_at = models.DateTimeField(_("Started At"), auto_now_add=True)
    completed_at = models.DateTimeField(_("Completed At"), null=True, blank=True)
    time_spent_seconds = models.PositiveIntegerField(_("Time Spent (seconds)"), default=0)
    
    # Status and quality
    status = models.CharField(_("Status"), max_length=20, choices=STATUS_CHOICES, default='started')
    quality_score = models.DecimalField(
        _("Quality Score"), max_digits=5, decimal_places=2, null=True, blank=True
    )
    
    # Rewards
    base_reward_earned = models.DecimalField(
        _("Base Reward Earned"), max_digits=10, decimal_places=2, default=0
    )
    bonus_reward_earned = models.DecimalField(
        _("Bonus Reward Earned"), max_digits=10, decimal_places=2, default=0
    )
    total_reward_earned = models.DecimalField(
        _("Total Reward Earned"), max_digits=10, decimal_places=2, default=0
    )
    
    # Quality flags
    failed_attention_checks = models.PositiveIntegerField(
        _("Failed Attention Checks"), default=0
    )
    flagged_for_speeding = models.BooleanField(_("Flagged for Speeding"), default=False)
    flagged_for_inconsistency = models.BooleanField(
        _("Flagged for Inconsistency"), default=False
    )
    
    # Review information
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_surveys'
    )
    review_notes = models.TextField(_("Review Notes"), blank=True)
    reviewed_at = models.DateTimeField(_("Reviewed At"), null=True, blank=True)
    
    class Meta:
        app_label = "cms"
        verbose_name = _("Survey Completion")
        verbose_name_plural = _("Survey Completions")
        ordering = ['-started_at']
        # unique_together removed: a user may have multiple attempts / retakes
        indexes = [
            models.Index(fields=['survey', 'status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'completed_at']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.survey.title} ({self.get_status_display()})"
    
    def calculate_reward(self) -> Decimal:
        """Calculate reward based on completion quality"""
        base_reward = self.survey.base_reward
        
        # Apply quality bonus
        if self.quality_score and self.quality_score >= 0.8:
            bonus = self.survey.bonus_reward
        else:
            bonus = Decimal('0')
        
        # Apply penalties for quality issues
        if self.flagged_for_speeding:
            base_reward *= Decimal('0.5')  # 50% penalty
        
        if self.failed_attention_checks > 0:
            penalty_per_check = Decimal('0.1')
            total_penalty = penalty_per_check * self.failed_attention_checks
            base_reward *= (Decimal('1') - min(total_penalty, Decimal('0.5')))  # Max 50% penalty
        
        return max(base_reward + bonus, Decimal('0'))
    
    def complete_survey(self, responses: dict, quality_score: Decimal = None):
        """Complete survey with responses"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.time_spent_seconds = int((self.completed_at - self.started_at).total_seconds())
        
        if quality_score is not None:
            self.quality_score = quality_score
        
        # Calculate rewards
        self.base_reward_earned = self.survey.base_reward
        self.bonus_reward_earned = self.survey.bonus_reward if quality_score and quality_score >= 0.8 else Decimal('0')
        self.total_reward_earned = self.calculate_reward()
        
        self.save()
        
        # Save responses — question_id keys may be UUID strings or integer PKs
        for question_id, answer in responses.items():
            try:
                # Try UUID first (most test data uses UUID keys)
                import uuid as _uuid
                try:
                    _uuid.UUID(str(question_id))
                    SurveyResponse.objects.create(
                        completion=self,
                        question=SurveyQuestion.objects.get(uuid=question_id),
                        answer=answer,
                    )
                except (ValueError, SurveyQuestion.DoesNotExist):
                    # Fall back to integer PK
                    SurveyResponse.objects.create(
                        completion=self,
                        question_id=int(question_id),
                        answer=answer,
                    )
            except Exception:
                # Skip malformed keys rather than aborting the whole completion
                pass


class SurveyResponse(models.Model):
    """
    Individual survey question responses
    """
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    completion = models.ForeignKey(SurveyCompletion, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(SurveyQuestion, on_delete=models.CASCADE, related_name='responses')
    
    # Response data
    answer = models.JSONField(_("Answer"))
    answer_text = models.TextField(_("Answer Text"), blank=True)
    answer_number = models.DecimalField(
        _("Answer Number"), max_digits=10, decimal_places=2, null=True, blank=True
    )
    
    # Metadata
    response_time_seconds = models.PositiveIntegerField(
        _("Response Time (seconds)"), null=True, blank=True
    )
    is_attention_check = models.BooleanField(_("Is Attention Check"), default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = "cms"
        verbose_name = _("Survey Response")
        verbose_name_plural = _("Survey Responses")
        ordering = ['completion', 'question__order']
        # unique_together removed — retakes produce multiple responses per question
        indexes = [
            models.Index(fields=['completion', 'question']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.completion.user.username} - {self.question.question_text[:50]}"


# Service class for profile-based surveys
class ProfileSurveyService:
    """
    Service for managing profile-based survey matching and recommendations
    """
    
    @staticmethod
    def get_recommended_surveys(user, limit: int = 10) -> list:
        """Get personalized survey recommendations for user"""
        # Get all active surveys
        surveys = SurveyTemplate.objects.filter(status='active').select_related('category')
        
        # Filter by user profile
        matching_surveys = []
        for survey in surveys:
            if survey.matches_user_profile(user):
                # Calculate match score
                match_score = ProfileSurveyService._calculate_match_score(survey, user)
                matching_surveys.append({
                    'survey': survey,
                    'match_score': match_score,
                    'estimated_reward': float(survey.base_reward + survey.bonus_reward),
                    'estimated_minutes': survey.estimated_minutes,
                    'completion_rate': float(survey.get_completion_rate()),
                })
        
        # Sort by match score and limit
        matching_surveys.sort(key=lambda x: x['match_score'], reverse=True)
        return matching_surveys[:limit]
    
    @staticmethod
    def _calculate_match_score(survey: SurveyTemplate, user) -> float:
        """Calculate how well a survey matches user profile"""
        try:
            profile = user.profile
        except AttributeError:
            return 0.0
        
        score = 0.0
        max_score = 0.0
        
        # Age matching (20 points)
        if survey.min_age or survey.max_age:
            max_score += 20
            if profile.age:
                if survey.min_age and survey.max_age:
                    if survey.min_age <= profile.age <= survey.max_age:
                        score += 20
                elif survey.min_age and profile.age >= survey.min_age:
                    score += 20
                elif survey.max_age and profile.age <= survey.max_age:
                    score += 20
        
        # Country matching (15 points)
        if survey.target_countries:
            max_score += 15
            if profile.country and profile.country in survey.target_countries:
                score += 15
        
        # Interest matching (25 points)
        if survey.target_interests:
            max_score += 25
            user_interests = getattr(profile, 'interests', [])
            matching_interests = len(set(survey.target_interests) & set(user_interests))
            if user_interests:
                score += (matching_interests / len(survey.target_interests)) * 25
        
        # Education matching (10 points)
        if survey.target_education:
            max_score += 10
            if profile.education and profile.education in survey.target_education:
                score += 10
        
        # Income level matching (10 points)
        if survey.target_income_levels:
            max_score += 10
            if profile.income_level and profile.income_level in survey.target_income_levels:
                score += 10
        
        # Gender matching (5 points)
        if survey.target_genders:
            max_score += 5
            if profile.gender and profile.gender in survey.target_genders:
                score += 5
        
        # Account age matching (10 points)
        if survey.min_account_age_days:
            max_score += 10
            account_age = (timezone.now() - user.date_joined).days
            if account_age >= survey.min_account_age_days:
                score += 10
        
        # Experience matching (5 points)
        if survey.min_completed_surveys:
            max_score += 5
            completed_count = SurveyCompletion.objects.filter(
                user=user, status='approved'
            ).count()
            if completed_count >= survey.min_completed_surveys:
                score += 5
        
        # Normalize to 0-100 scale
        if max_score > 0:
            return min((score / max_score) * 100, 100)
        
        return 0.0
    
    @staticmethod
    def create_survey_completion(user, survey_uuid: str, responses: dict) -> SurveyCompletion:
        """Create and process survey completion"""
        try:
            survey = SurveyTemplate.objects.get(uuid=survey_uuid, status='active')
        except SurveyTemplate.DoesNotExist:
            raise ValueError("Survey not found or not active")
        
        # Check if user already completed this survey
        if SurveyCompletion.objects.filter(survey=survey, user=user).exists():
            raise ValueError("User has already completed this survey")
        
        # Create completion
        completion = SurveyCompletion.objects.create(
            survey=survey,
            user=user
        )
        
        # Analyze responses for quality
        quality_score = ProfileSurveyService._analyze_response_quality(responses, survey)
        
        # Complete survey with responses
        completion.complete_survey(responses, quality_score)
        
        return completion
    
    @staticmethod
    def _analyze_response_quality(responses: dict, survey: SurveyTemplate) -> Decimal:
        """Analyze response quality and return score (0-1)"""
        score = Decimal('1.0')
        
        # Check for speeding (too fast completion)
        if survey.min_time_seconds:
            total_questions = survey.questions.count()
            min_total_time = survey.min_time_seconds * total_questions
            # This would need timing data per question
            # For now, assume reasonable completion time
        
        # Check for straight-lining (same answer for all questions)
        if len(responses) > 1:
            answers = list(responses.values())
            if all(isinstance(answer, str) for answer in answers):
                if len(set(answers)) == 1:
                    score -= Decimal('0.2')  # 20% penalty
        
        # Check for inconsistent answers
        # This would need more complex logic based on question types
        
        return max(score, Decimal('0'))
    
    @staticmethod
    def get_survey_analytics(survey_uuid: str) -> dict:
        """Get comprehensive analytics for a survey"""
        try:
            survey = SurveyTemplate.objects.get(uuid=survey_uuid)
        except SurveyTemplate.DoesNotExist:
            return {}
        
        # Basic stats
        total_started = SurveyCompletion.objects.filter(survey=survey).count()
        total_completed = SurveyCompletion.objects.filter(survey=survey, status='completed').count()
        total_approved = SurveyCompletion.objects.filter(survey=survey, status='approved').count()
        
        completion_rate = (total_completed / total_started * 100) if total_started > 0 else 0
        approval_rate = (total_approved / total_completed * 100) if total_completed > 0 else 0
        
        # Time analytics
        avg_time = SurveyCompletion.objects.filter(
            survey=survey, status='approved'
        ).aggregate(avg=Avg('time_spent_seconds'))['avg'] or 0
        
        # Quality analytics
        avg_quality = SurveyCompletion.objects.filter(
            survey=survey, status='approved'
        ).aggregate(avg=Avg('quality_score'))['avg'] or 0
        
        # Demographics
        demographics = {}
        for completion in SurveyCompletion.objects.filter(survey=survey, status='approved').select_related('user__profile'):
            profile = completion.user.profile
            # Aggregate demographic data
        
        return {
            'survey_uuid': str(survey.uuid),
            'title': survey.title,
            'total_started': total_started,
            'total_completed': total_completed,
            'total_approved': total_approved,
            'completion_rate': round(completion_rate, 2),
            'approval_rate': round(approval_rate, 2),
            'avg_time_seconds': round(avg_time, 2),
            'avg_quality_score': round(float(avg_quality), 2),
            'total_payout': float(total_approved * survey.base_reward),
            'demographics': demographics,
        }


# Backward-compat alias
Survey = SurveyTemplate
