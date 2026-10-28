# api/cms/querysets.py
"""Custom querysets for CMS models."""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from django.db import models
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum, F, ExpressionWrapper, FloatField

logger = logging.getLogger(__name__)


# ── Original QuerySets (Enhanced) ─────────────────────────────────────

class TimestampedQuerySet(models.QuerySet):
    def recent(self, days=7):
        from datetime import timedelta
        return self.filter(created_at__gte=timezone.now() - timedelta(days=days))

    def today(self):
        return self.filter(created_at__date=timezone.now().date())

    def this_month(self):
        now = timezone.now()
        return self.filter(created_at__year=now.year, created_at__month=now.month)


class ActiveQuerySet(TimestampedQuerySet):
    def active(self):
        return self.filter(is_active=True)

    def inactive(self):
        return self.filter(is_active=False)


class PublishedQuerySet(ActiveQuerySet):
    def published(self):
        return self.filter(status='published', published_at__lte=timezone.now())

    def draft(self):
        return self.filter(status='draft')

    def scheduled(self):
        return self.filter(status='scheduled', published_at__gt=timezone.now())


class ConversionQuerySet(TimestampedQuerySet):
    def approved(self):
        return self.filter(status='approved')

    def rejected(self):
        return self.filter(status__in=['rejected', 'fraud', 'duplicate'])

    def pending(self):
        return self.filter(status='pending')

    def for_user(self, user):
        return self.filter(user=user)


# ── Enhanced QuerySet Classes ─────────────────────────────────────

class BaseCMSQuerySet(models.QuerySet):
    """Base queryset for CMS models with common functionality."""
    
    def active(self) -> 'BaseCMSQuerySet':
        """Filter for active records."""
        return self.filter(is_active=True)
    
    def inactive(self) -> 'BaseCMSQuerySet':
        """Filter for inactive records."""
        return self.filter(is_active=False)
    
    def recent(self, days: int = 7) -> 'BaseCMSQuerySet':
        """Filter for recent records within specified days."""
        since = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=since)
    
    def with_counts(self) -> 'BaseCMSQuerySet':
        """Add count annotations."""
        return self.annotate(
            total_count=Count('id')
        )
    
    def search(self, query: str, fields: List[str] = None) -> 'BaseCMSQuerySet':
        """Search across specified fields."""
        if not query or not fields:
            return self
        
        q_objects = Q()
        for field in fields:
            q_objects |= Q(**{f"{field}__icontains": query})
        
        return self.filter(q_objects)


class SoftDeleteQuerySet(BaseCMSQuerySet):
    """QuerySet for models with soft delete functionality."""
    
    def deleted(self) -> 'SoftDeleteQuerySet':
        """Filter for deleted records."""
        return self.filter(is_deleted=True)
    
    def not_deleted(self) -> 'SoftDeleteQuerySet':
        """Filter for non-deleted records."""
        return self.filter(is_deleted=False)
    
    def with_deleted_at(self) -> 'SoftDeleteQuerySet':
        """Include deleted_at field."""
        return self.annotate(
            deleted_at=F('deleted_at')
        )


# ── User QuerySets ─────────────────────────────────────

class UserQuerySet(BaseCMSQuerySet):
    """QuerySet for User model."""
    
    def staff(self) -> 'UserQuerySet':
        """Filter for staff users."""
        return self.filter(is_staff=True)
    
    def superusers(self) -> 'UserQuerySet':
        """Filter for superusers."""
        return self.filter(is_superuser=True)
    
    def regular_users(self) -> 'UserQuerySet':
        """Filter for regular (non-staff) users."""
        return self.filter(is_staff=False, is_superuser=False)
    
    def active_users(self) -> 'UserQuerySet':
        """Filter for active users."""
        return self.filter(is_active=True)
    
    def inactive_users(self) -> 'UserQuerySet':
        """Filter for inactive users."""
        return self.filter(is_active=False)
    
    def recently_joined(self, days: int = 30) -> 'UserQuerySet':
        """Filter for users who joined recently."""
        since = timezone.now() - timedelta(days=days)
        return self.filter(date_joined__gte=since)
    
    def with_profile_completeness(self) -> 'UserQuerySet':
        """Include profile completeness percentage."""
        return self.annotate(
            profile_completeness=F('userprofile__completeness_percentage')
        )
    
    def with_survey_stats(self) -> 'UserQuerySet':
        """Include survey completion statistics."""
        return self.annotate(
            total_surveys=Count('survey_completions'),
            completed_surveys=Count('survey_completions', filter=Q(survey_completions__status='completed')),
            avg_quality_score=Avg('survey_completions__quality_score', filter=Q(survey_completions__status='completed'))
        )


# ── Survey QuerySets ─────────────────────────────────────

class SurveyQuerySet(BaseCMSQuerySet):
    """QuerySet for Survey model."""
    
    def published(self) -> 'SurveyQuerySet':
        """Filter for published surveys."""
        return self.filter(status='published')
    
    def draft(self) -> 'SurveyQuerySet':
        """Filter for draft surveys."""
        return self.filter(status='draft')
    
    def active(self) -> 'SurveyQuerySet':
        """Filter for active surveys."""
        return self.filter(status='active')
    
    def public(self) -> 'SurveyQuerySet':
        """Filter for public surveys."""
        return self.filter(is_public=True)
    
    def private(self) -> 'SurveyQuerySet':
        """Filter for private surveys."""
        return self.filter(is_public=False)
    
    def by_difficulty(self, difficulty: str) -> 'SurveyQuerySet':
        """Filter by difficulty level."""
        return self.filter(difficulty=difficulty)
    
    def by_category(self, category_id: int) -> 'SurveyQuerySet':
        """Filter by category."""
        return self.filter(category_id=category_id)
    
    def with_participant_count(self) -> 'SurveyQuerySet':
        """Include participant count."""
        return self.annotate(
            participant_count=Count('survey_completions'),
            completion_count=Count('survey_completions', filter=Q(survey_completions__status='completed'))
        )
    
    def with_avg_quality_score(self) -> 'SurveyQuerySet':
        """Include average quality score."""
        return self.annotate(
            avg_quality_score=Avg('survey_completions__quality_score', filter=Q(survey_completions__status='completed'))
        )
    
    def with_reward_range(self) -> 'SurveyQuerySet':
        """Include reward range."""
        return self.annotate(
            min_reward_display=F('min_reward'),
            max_reward_display=F('max_reward')
        )
    
    def available_to_user(self, user) -> 'SurveyQuerySet':
        """Filter surveys available to specific user."""
        # Exclude surveys user has already completed
        completed_survey_ids = user.survey_completions.filter(
            status='completed'
        ).values_list('survey_id', flat=True)
        
        return self.exclude(id__in=completed_survey_ids).active().public()


class SurveyCompletionQuerySet(BaseCMSQuerySet):
    """QuerySet for SurveyCompletion model."""
    
    def completed(self) -> 'SurveyCompletionQuerySet':
        """Filter for completed surveys."""
        return self.filter(status='completed')
    
    def in_progress(self) -> 'SurveyCompletionQuerySet':
        """Filter for surveys in progress."""
        return self.filter(status='in_progress')
    
    def abandoned(self) -> 'SurveyCompletionQuerySet':
        """Filter for abandoned surveys."""
        return self.filter(status='abandoned')
    
    def by_user(self, user) -> 'SurveyCompletionQuerySet':
        """Filter by user."""
        return self.filter(user=user)
    
    def by_survey(self, survey) -> 'SurveyCompletionQuerySet':
        """Filter by survey."""
        return self.filter(survey=survey)
    
    def high_quality(self, threshold: float = 0.8) -> 'SurveyCompletionQuerySet':
        """Filter for high quality completions."""
        return self.filter(quality_score__gte=threshold)
    
    def completed_today(self) -> 'SurveyCompletionQuerySet':
        """Filter for completions completed today."""
        today = timezone.now().date()
        return self.filter(
            status='completed',
            completed_at__date=today
        )
    
    def completed_this_week(self) -> 'SurveyCompletionQuerySet':
        """Filter for completions completed this week."""
        week_start = timezone.now() - timedelta(days=timezone.now().weekday())
        return self.filter(
            status='completed',
            completed_at__gte=week_start
        )
    
    def with_duration(self) -> 'SurveyCompletionQuerySet':
        """Include duration calculation."""
        return self.annotate(
            duration_seconds=ExpressionWrapper(
                F('completed_at') - F('started_at'),
                output_field=FloatField()
            )
        )
    
    def with_reward_earned(self) -> 'SurveyCompletionQuerySet':
        """Include reward amount earned."""
        return self.annotate(
            reward_earned=Sum('reward_transactions__amount', filter=Q(reward_transactions__transaction_type='earned'))
        )


# ── Reward QuerySets ─────────────────────────────────────

class RewardTransactionQuerySet(BaseCMSQuerySet):
    """QuerySet for RewardTransaction model."""
    
    def earned(self) -> 'RewardTransactionQuerySet':
        """Filter for earned rewards."""
        return self.filter(transaction_type='earned')
    
    def payout(self) -> 'RewardTransactionQuerySet':
        """Filter for payout transactions."""
        return self.filter(transaction_type='payout')
    
    def bonus(self) -> 'RewardTransactionQuerySet':
        """Filter for bonus rewards."""
        return self.filter(transaction_type='bonus')
    
    def penalty(self) -> 'RewardTransactionQuerySet':
        """Filter for penalty transactions."""
        return self.filter(transaction_type='penalty')
    
    def by_user(self, user) -> 'RewardTransactionQuerySet':
        """Filter by user."""
        return self.filter(user=user)
    
    def by_status(self, status: str) -> 'RewardTransactionQuerySet':
        """Filter by status."""
        return self.filter(status=status)
    
    def completed(self) -> 'RewardTransactionQuerySet':
        """Filter for completed transactions."""
        return self.filter(status='completed')
    
    def pending(self) -> 'RewardTransactionQuerySet':
        """Filter for pending transactions."""
        return self.filter(status='pending')
    
    def failed(self) -> 'RewardTransactionQuerySet':
        """Filter for failed transactions."""
        return self.filter(status='failed')
    
    def this_month(self) -> 'RewardTransactionQuerySet':
        """Filter for transactions this month."""
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return self.filter(created_at__gte=month_start)
    
    def with_user_balance(self) -> 'RewardTransactionQuerySet':
        """Include user balance calculation."""
        return self.annotate(
            earned_amount=Sum('amount', filter=Q(transaction_type='earned', status='completed')),
            paid_amount=Sum('amount', filter=Q(transaction_type='payout', status='completed')),
            net_balance=ExpressionWrapper(
                Sum('amount', filter=Q(transaction_type='earned', status='completed')) - 
                Sum('amount', filter=Q(transaction_type='payout', status='completed')),
                output_field=FloatField()
            )
        )


# ── User Profile QuerySets ─────────────────────────────────────

class UserProfileQuerySet(BaseCMSQuerySet):
    """QuerySet for UserProfile model."""
    
    def complete(self, threshold: float = 80.0) -> 'UserProfileQuerySet':
        """Filter for profiles with high completeness."""
        return self.filter(completeness_percentage__gte=threshold)
    
    def incomplete(self, threshold: float = 50.0) -> 'UserProfileQuerySet':
        """Filter for profiles with low completeness."""
        return self.filter(completeness_percentage__lt=threshold)
    
    def by_country(self, country: str) -> 'UserProfileQuerySet':
        """Filter by country."""
        return self.filter(country__iexact=country)
    
    def by_city(self, city: str) -> 'UserProfileQuerySet':
        """Filter by city."""
        return self.filter(city__iexact=city)
    
    def with_age_range(self, min_age: int = None, max_age: int = None) -> 'UserProfileQuerySet':
        """Filter by age range."""
        queryset = self
        
        if min_age is not None:
            min_birthdate = timezone.now() - timedelta(days=min_age * 365)
            queryset = queryset.filter(date_of_birth__lte=min_birthdate)
        
        if max_age is not None:
            max_birthdate = timezone.now() - timedelta(days=max_age * 365)
            queryset = queryset.filter(date_of_birth__gte=max_birthdate)
        
        return queryset
    
    def with_segments(self) -> 'UserProfileQuerySet':
        """Include user segments."""
        return self.prefetch_related('user_segments')
    
    def with_survey_stats(self) -> 'UserProfileQuerySet':
        """Include survey statistics."""
        return self.annotate(
            total_surveys=Count('user__survey_completions'),
            completed_surveys=Count('user__survey_completions', filter=Q(user__survey_completions__status='completed')),
            total_earned=Sum('user__reward_transactions__amount', filter=Q(user__reward_transactions__transaction_type='earned'))
        )


# ── QuerySet Utilities ─────────────────────────────────────

class QuerySetUtils:
    """Utilities for working with querysets."""
    
    @staticmethod
    def bulk_update_with_timestamp(queryset: models.QuerySet, **fields) -> int:
        """Bulk update with automatic timestamp update."""
        if hasattr(queryset.model, 'updated_at'):
            fields['updated_at'] = timezone.now()
        
        return queryset.bulk_update(list(queryset), fields)
    
    @staticmethod
    def soft_delete(queryset: models.QuerySet) -> int:
        """Soft delete records."""
        if hasattr(queryset.model, 'is_deleted'):
            return queryset.update(is_deleted=True, deleted_at=timezone.now())
        else:
            return queryset.delete()[0]
    
    @staticmethod
    def get_or_create_with_defaults(queryset: models.QuerySet, defaults: Dict[str, Any], **kwargs) -> tuple:
        """Get or create with defaults."""
        return queryset.get_or_create(defaults=defaults, **kwargs)
    
    @staticmethod
    def annotate_with_percentage(queryset: models.QuerySet, numerator_field: str, denominator_field: str, 
                           output_field: str) -> models.QuerySet:
        """Annotate queryset with percentage calculation."""
        return queryset.annotate(**{
            output_field: ExpressionWrapper(
                (F(numerator_field) / F(denominator_field)) * 100,
                output_field=FloatField()
            )
        })
    
    @staticmethod
    def get_date_range_queryset(queryset: models.QuerySet, days: int) -> models.QuerySet:
        """Get queryset filtered by date range."""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        return queryset.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
    
    @staticmethod
    def get_top_n(queryset: models.QuerySet, field: str, n: int = 10) -> models.QuerySet:
        """Get top N records by field."""
        return queryset.order_by(f'-{field}')[:n]
    
    @staticmethod
    def get_random_sample(queryset: models.QuerySet, n: int) -> models.QuerySet:
        """Get random sample of N records."""
        return queryset.order_by('?')[:n]


# ── QuerySet Performance Utilities ─────────────────────────────────────

class QuerySetPerformanceUtils:
    """Utilities for optimizing queryset performance."""
    
    @staticmethod
    def optimize_for_list(queryset: models.QuerySet) -> models.QuerySet:
        """Optimize queryset for list display."""
        return queryset.select_related().prefetch_related()
    
    @staticmethod
    def optimize_for_count(queryset: models.QuerySet) -> models.QuerySet:
        """Optimize queryset for counting."""
        return queryset.only('id')
    
    @staticmethod
    def optimize_for_export(queryset: models.QuerySet, fields: List[str] = None) -> models.QuerySet:
        """Optimize queryset for data export."""
        if fields:
            return queryset.only(*fields)
        return queryset.select_related().prefetch_related()
    
    @staticmethod
    def batch_process(queryset: models.QuerySet, batch_size: int = 1000, 
                   processor_func: callable = None) -> None:
        """Process queryset in batches."""
        if not processor_func:
            return
        
        offset = 0
        while True:
            batch = list(queryset[offset:offset + batch_size])
            if not batch:
                break
            
            processor_func(batch)
            offset += batch_size

    def with_payout_total(self):
        from django.db.models import Sum
        return self.aggregate(total=Sum('payout_usd'))['total'] or 0

    def high_value(self, min_usd=1.0):
        return self.filter(payout_usd__gte=min_usd)


class LeaderboardQuerySet(models.QuerySet):
    def ranked(self):
        return self.filter(rank__gt=0).order_by('rank')

    def top(self, n=10):
        return self.ranked()[:n]

    def by_category(self, category):
        return self.filter(category=category)

    def with_user_info(self):
        return self.select_related('user', 'period')


class VirtualTransactionQuerySet(TimestampedQuerySet):
    def earnings(self):
        return self.filter(tx_type__startswith='earn_')

    def withdrawals(self):
        return self.filter(tx_type__startswith='spend_')

    def for_user(self, user):
        return self.filter(user=user)

    def total_earned(self):
        from django.db.models import Sum
        return self.earnings().aggregate(t=Sum('amount'))['t'] or 0


class OfferCacheQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def featured(self):
        return self.filter(is_featured=True)

    def quizzes(self):
        return self.filter(is_quiz=True)

    def for_country(self, country_code):
        from django.db.models import Q
        return self.filter(
            Q(countries=[]) | Q(countries__contains=country_code.upper())
        )

    def for_device(self, device):
        from django.db.models import Q
        return self.filter(
            Q(devices=[]) | Q(devices__contains=device.lower())
        )

    def by_type(self, offer_type):
        return self.filter(offer_type=offer_type)

    def ordered_by_payout(self):
        return self.order_by('-is_featured', '-payout_usd')


class SmartLinkQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def with_stats(self):
        return self.prefetch_related('routing_rules', 'clicks')


class QuizAttemptQuerySet(TimestampedQuerySet):
    def completed(self):
        return self.filter(is_completed=True)

    def incomplete(self):
        return self.filter(is_completed=False)

    def rewarded(self):
        return self.filter(reward_earned=True)

    def for_user(self, user):
        return self.filter(user=user)


class WithdrawalQuerySet(TimestampedQuerySet):
    def pending(self):
        return self.filter(status='pending')

    def paid(self):
        return self.filter(status='paid')

    def by_method(self, method):
        return self.filter(method=method)

    def for_user(self, user):
        return self.filter(user=user)

    def total_paid(self):
        from django.db.models import Sum
        return self.paid().aggregate(t=Sum('net_usd'))['t'] or 0
