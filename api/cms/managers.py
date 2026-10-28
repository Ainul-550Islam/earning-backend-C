# api/cms/managers.py
"""Custom Django model managers and querysets for CMS."""
from django.db import models
from django.utils import timezone
from django.core.cache import cache


class ActiveManager(models.Manager):
    """Returns only active (is_active=True) objects."""
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class PublishedManager(models.Manager):
    """Returns published content ordered by date."""
    def get_queryset(self):
        return super().get_queryset().filter(
            status='published',
            published_at__lte=timezone.now()
        ).order_by('-published_at')


class ConversionLogManager(models.Manager):
    """Manager for CPAlead ConversionLog with useful querysets."""

    def approved(self):
        return self.filter(status='approved')

    def pending(self):
        return self.filter(status='pending')

    def for_user(self, user):
        return self.filter(user=user)

    def today(self):
        return self.filter(created_at__date=timezone.now().date())

    def this_week(self):
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=7)
        return self.filter(created_at__gte=cutoff)

    def total_payout(self):
        from django.db.models import Sum
        return self.approved().aggregate(total=Sum('payout_usd'))['total'] or 0


class ClickLogManager(models.Manager):
    def unconverted(self):
        return self.filter(has_converted=False)


class SurveyManager(models.Manager):
    """Manager for Survey models with useful querysets."""
    
    def active(self):
        return self.filter(status='active')
    
    def available_for_user(self, user):
        """Get surveys available for a specific user."""
        return self.active().exclude(
            models.Q(surveycompletion__user=user, surveycompletion__status='completed') |
            models.Q(surveycompletion__user=user, surveycompletion__status='approved')
        )
    
    def by_category(self, category_uuid):
        return self.filter(category__uuid=category_uuid)
    
    def by_reward_range(self, min_reward, max_reward):
        return self.filter(
            models.Q(min_reward__gte=min_reward) &
            models.Q(max_reward__lte=max_reward)
        )
    
    def recent(self, days=30):
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)


class SurveyCompletionManager(models.Manager):
    """Manager for SurveyCompletion models."""
    
    def by_user(self, user):
        return self.filter(user=user)
    
    def by_status(self, status):
        return self.filter(status=status)
    
    def completed_today(self):
        return self.filter(
            status='completed',
            completed_at__date=timezone.now().date()
        )
    
    def high_quality(self, min_score=0.8):
        return self.filter(quality_score__gte=min_score)
    
    def pending_approval(self):
        return self.filter(status='completed', quality_score__gte=0.7)
    
    def total_rewards_earned(self, user=None):
        from django.db.models import Sum
        queryset = self.filter(status='approved')
        if user:
            queryset = queryset.filter(user=user)
        return queryset.aggregate(total=Sum('total_reward_earned'))['total'] or 0


class UserProfileManager(models.Manager):
    """Manager for UserProfile models."""
    
    def complete(self, min_completeness=50):
        return self.filter(profile_completeness__gte=min_completeness)
    
    def by_country(self, country):
        return self.filter(country=country)
    
    def by_education(self, education):
        return self.filter(education=education)
    
    def by_income_level(self, income_level):
        return self.filter(income_level=income_level)
    
    def with_interests(self, interests):
        return self.filter(interests__overlap=interests)
    
    def high_participation(self, min_score=50):
        return self.filter(survey_participation_score__gte=min_score)
    
    def high_quality(self, min_score=0.8):
        return self.filter(quality_score__gte=min_score)


class UserSegmentManager(models.Manager):
    """Manager for UserSegment models."""
    
    def active(self):
        return self.filter(is_active=True)
    
    def with_min_users(self, min_users=10):
        return self.filter(user_count__gte=min_users)
    
    def by_creator(self, user):
        return self.filter(created_by=user)
    
    def recent(self, days=30):
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)


class RewardTransactionManager(models.Manager):
    """Manager for RewardTransaction models."""
    
    def by_user(self, user):
        return self.filter(user=user)
    
    def by_status(self, status):
        return self.filter(status=status)
    
    def by_type(self, transaction_type):
        return self.filter(transaction_type=transaction_type)
    
    def pending(self):
        return self.filter(status='pending')
    
    def approved(self):
        return self.filter(status='approved')
    
    def paid(self):
        return self.filter(status='paid')
    
    def total_amount(self, user=None, status=None):
        from django.db.models import Sum
        queryset = self.all()
        if user:
            queryset = queryset.filter(user=user)
        if status:
            queryset = queryset.filter(status=status)
        return queryset.aggregate(total=Sum('amount'))['total'] or 0
    
    def recent(self, days=30):
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)


class RewardPoolManager(models.Manager):
    """Manager for RewardPool models."""
    
    def active(self):
        return self.filter(is_active=True)
    
    def low_funds(self, threshold=20):
        """Return pools with less than threshold percentage remaining."""
        return self.active().annotate(
            utilization=models.F('allocated_amount') * 100.0 / models.F('total_budget')
        ).filter(utilization__gte=(100 - threshold))
    
    def needs_refill(self):
        return self.active().filter(
            models.Q(allocated_amount__gte=models.F('total_budget') * 0.8) |
            models.Q(auto_refill=True)
        )
    
    def by_currency(self, currency_uuid):
        return self.filter(currency__uuid=currency_uuid)


class TaskScheduleManager(models.Manager):
    """Manager for TaskSchedule models."""
    
    def active(self):
        return self.filter(status='active')
    
    def ready_to_run(self):
        return self.active().filter(
            models.Q(next_run__lte=timezone.now()) |
            models.Q(next_run__isnull=True)
        )
    
    def by_frequency(self, frequency):
        return self.filter(frequency=frequency)
    
    def by_priority(self, priority):
        return self.filter(priority=priority)
    
    def failed_recently(self, hours=24):
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(
            taskexecution__status='failure',
            taskexecution__started_at__gte=cutoff
        ).distinct()


class TaskExecutionManager(models.Manager):
    """Manager for TaskExecution models."""
    
    def by_status(self, status):
        return self.filter(status=status)
    
    def by_worker(self, worker_id):
        return self.filter(worker_id=worker_id)
    
    def running(self):
        return self.filter(status='running')
    
    def failed(self):
        return self.filter(status='failure')
    
    def successful(self):
        return self.filter(status='success')
    
    def recent(self, hours=24):
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(started_at__gte=cutoff)
    
    def average_runtime(self, task_uuid=None):
        from django.db.models import Avg
        queryset = self.filter(status='success')
        if task_uuid:
            queryset = queryset.filter(schedule__uuid=task_uuid)
        return queryset.aggregate(avg=Avg('runtime_seconds'))['avg'] or 0


class TaskQueueManager(models.Manager):
    """Manager for TaskQueue models."""
    
    def queued(self):
        return self.filter(status='queued')
    
    def processing(self):
        return self.filter(status='processing')
    
    def failed(self):
        return self.filter(status='failed')
    
    def by_priority(self, priority):
        return self.filter(priority=priority)
    
    def by_queue(self, queue_name):
        return self.filter(queue_name=queue_name)
    
    def overdue(self, hours=1):
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(
            status='queued',
            queued_at__lte=cutoff
        )
    
    def high_retry_count(self, max_retries=3):
        return self.filter(retry_count__gte=max_retries)


class TaskLockManager(models.Manager):
    """Manager for TaskLock models."""
    
    def active(self):
        return self.filter(expires_at__gte=timezone.now())
    
    def expired(self):
        return self.filter(expires_at__lt=timezone.now())
    
    def by_owner(self, owner):
        return self.filter(owner=owner)
    
    def by_task(self, task_name):
        return self.filter(task_name=task_name)
    
    def cleanup_expired(self):
        """Delete all expired locks."""
        return self.expired().delete()
    
    def acquire_lock(self, lock_key, owner, timeout_seconds=300):
        """Try to acquire a lock."""
        from datetime import timedelta
        expires_at = timezone.now() + timedelta(seconds=timeout_seconds)
        
        return self.create(
            lock_key=lock_key,
            owner=owner,
            expires_at=expires_at
        )
    
    def release_lock(self, lock_key):
        """Release a specific lock."""
        return self.filter(lock_key=lock_key).delete()

    def converted(self):
        return self.filter(has_converted=True)

    def not_fraud(self):
        return self.filter(is_fraud=False)

    def for_user(self, user):
        return self.filter(user=user)


class LeaderboardEntryManager(models.Manager):
    def ranked(self):
        return self.filter(rank__gt=0).order_by('rank')

    def top(self, n=10):
        return self.ranked()[:n]

    def for_period_type(self, period_type='weekly'):
        from api.cms.models_new.leaderboard import LeaderboardPeriod
        period = LeaderboardPeriod.get_active(period_type)
        if not period:
            return self.none()
        return self.filter(period=period)


class ReferralEarningManager(models.Manager):
    def for_referrer(self, user):
        return self.filter(referrer=user)

    def this_month(self):
        today = timezone.now().date()
        return self.filter(
            created_at__year=today.year,
            created_at__month=today.month
        )

    def total_bonus(self, user):
        from django.db.models import Sum
        return self.for_referrer(user).aggregate(
            total=Sum('bonus_usd')
        )['total'] or 0


class WithdrawalRequestManager(models.Manager):
    def pending(self):
        return self.filter(status='pending')

    def paid(self):
        return self.filter(status='paid')

    def for_user(self, user):
        return self.filter(user=user)

    def awaiting_approval(self):
        return self.filter(status__in=['pending', 'approved'])


class QuizAttemptManager(models.Manager):
    def completed(self):
        return self.filter(is_completed=True)

    def incomplete(self):
        return self.filter(is_completed=False)

    def for_user(self, user):
        return self.filter(user=user)

    def for_quiz(self, quiz):
        return self.filter(quiz=quiz)


class ContentBlockManager(models.Manager):
    def for_page(self, page_id):
        return self.filter(parent_type='page', parent_id=page_id, is_visible=True).order_by('order')

    def for_blog(self, post_id):
        return self.filter(parent_type='blog_post', parent_id=post_id, is_visible=True).order_by('order')

    def visible(self):
        return self.filter(is_visible=True)


class FormSubmissionManager(models.Manager):
    def for_form(self, form):
        return self.filter(form=form)

    def by_user(self, user):
        return self.filter(user=user)

    def today(self):
        return self.filter(submitted_at__date=timezone.now().date())


# =============================================================================
# querysets.py INTEGRATION — v9 PRODUCTION FIX
# -----------------------------------------------------------------------------
# querysets.py defined 8 custom QuerySet classes (TimestampedQuerySet,
# ActiveQuerySet, PublishedQuerySet, ConversionQuerySet, BaseCMSQuerySet,
# SoftDeleteQuerySet, UserQuerySet, SurveyQuerySet) but they were
# NEVER attached to any model as a manager.
#
# This section creates .from_queryset() managers for each QuerySet
# so they can be used as model.objects.today(), model.objects.published(),
# model.objects.search(), etc.
# =============================================================================

try:
    from .querysets import (
        TimestampedQuerySet, ActiveQuerySet, PublishedQuerySet,
        ConversionQuerySet, BaseCMSQuerySet, SoftDeleteQuerySet,
        UserQuerySet, SurveyQuerySet,
    )

    # ── Ready-to-use Manager classes (attach to your models) ─────────────────

    class TimestampedManager(models.Manager.from_queryset(TimestampedQuerySet)):
        """Use on any model with created_at/updated_at fields.
        Adds: .recent(days), .today(), .this_month()"""
        pass

    class ActiveTimestampedManager(models.Manager.from_queryset(ActiveQuerySet)):
        """Use on any model with is_active + timestamps.
        Adds: .active(), .inactive(), .recent(), .today()"""
        pass

    class PublishedContentManager(models.Manager.from_queryset(PublishedQuerySet)):
        """Use on content models (BlogPost, ContentPage, Banner, Popup).
        Adds: .published(), .draft(), .scheduled()"""
        def get_queryset(self):
            return super().get_queryset().filter(
                status='published',
            )

    class ConversionLogQSManager(models.Manager.from_queryset(ConversionQuerySet)):
        """Use on ConversionLog model.
        Adds: .approved(), .rejected(), .pending(), .for_user(user)"""
        pass

    class CMSBaseManager(models.Manager.from_queryset(BaseCMSQuerySet)):
        """Use on any CMS model.
        Adds: .active(), .inactive(), .recent(), .with_counts(), .search()"""
        pass

    class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
        """Use on models with soft-delete (deleted_at field).
        Adds: .deleted(), .not_deleted(), .with_deleted_at()
        Default queryset excludes deleted records."""
        def get_queryset(self):
            return super().get_queryset().not_deleted()

    class AllObjectsSoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
        """Like SoftDeleteManager but includes deleted records.
        Assign as model.all_objects to allow admin access to deleted rows."""
        pass

    class UserQSManager(models.Manager.from_queryset(UserQuerySet)):
        """Use on custom User proxy or UserProfile.
        Adds: .staff(), .superusers(), .regular_users(), .active_users(),
              .recently_joined(), .with_profile_completeness(), .with_survey_stats()"""
        pass

    class SurveyQSManager(models.Manager.from_queryset(SurveyQuerySet)):
        """Use on Survey / SurveyTemplate models.
        Adds: .published(), .draft(), .active(), .public()"""
        pass

    # ── How to attach these to your models ───────────────────────────────────
    # In models_new/blog.py:
    #   from api.cms.managers import PublishedContentManager, CMSBaseManager
    #   class BlogPost(models.Model):
    #       objects = PublishedContentManager()   # default: only published
    #       all_objects = CMSBaseManager()        # bypass filter for admin
    #
    # In models.py ConversionLog:
    #   from api.cms.managers import ConversionLogQSManager
    #   objects = ConversionLogQSManager()
    #
    # In models_new/profile_surveys.py Survey:
    #   from api.cms.managers import SurveyQSManager
    #   objects = SurveyQSManager()

except ImportError as _e:
    import logging
    logging.getLogger('cms.managers').warning(
        f'[managers.py] querysets.py import failed: {_e}'
    )
