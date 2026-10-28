# api/cms/events.py
"""
CMS Event definitions — typed event classes for type-safe publishing.

FIX (audit): 35+ event dataclasses were defined here but publish_event()
was never called from any service, making the entire event system dead code.

Solution:
  1. All existing event dataclasses are preserved exactly.
  2. A set of fire_*() convenience functions is added below them.
     Each function constructs the right event dataclass and calls publish_event().
  3. Services can now fire events in one line:
       from api.cms.events import fire_reward_earned
       fire_reward_earned(user=user, amount=5.00, source_type='offer')
  4. The existing publish_event() function is unchanged.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, List
from django.utils import timezone


# ══════════════════════════════════════════════════════════════════════════════
# Base event
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CMSEvent:
    event_type: str
    timestamp: str = field(default_factory=lambda: timezone.now().isoformat())
    source: str = 'cms'


# ══════════════════════════════════════════════════════════════════════════════
# Offer / Reward events
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RewardEarnedEvent(CMSEvent):
    event_type: str = 'reward_earned'
    user_id: Optional[int] = None
    amount: float = 0.0
    currency: str = 'USD'
    source_type: str = ''
    lead_id: str = ''
    virtual_amount: float = 0.0
    campaign_id: str = ''
    transaction_id: str = ''
    earned_at: str = ''


@dataclass
class RewardApprovedEvent(CMSEvent):
    event_type: str = 'reward_approved'
    user_id: Optional[int] = None
    transaction_id: str = ''
    amount: float = 0.0
    approved_by: Optional[int] = None
    approved_at: str = ''


@dataclass
class RewardPaidEvent(CMSEvent):
    event_type: str = 'reward_paid'
    user_id: Optional[int] = None
    transaction_id: str = ''
    amount: float = 0.0
    payment_method: str = ''
    paid_at: str = ''


@dataclass
class RewardPoolLowEvent(CMSEvent):
    event_type: str = 'reward_pool_low'
    pool_id: str = ''
    pool_name: str = ''
    utilization_percentage: float = 0.0
    remaining_amount: float = 0.0
    alert_at: str = ''


@dataclass
class RewardPoolRefilledEvent(CMSEvent):
    event_type: str = 'reward_pool_refilled'
    pool_id: str = ''
    pool_name: str = ''
    refill_amount: float = 0.0
    new_total: float = 0.0
    refilled_by: Optional[int] = None
    refilled_at: str = ''


@dataclass
class RewardTransactionCreatedEvent(CMSEvent):
    event_type: str = 'reward_transaction_created'
    user_id: Optional[int] = None
    transaction_id: str = ''
    amount: float = 0.0
    transaction_type: str = ''
    status: str = ''
    created_at: str = ''


@dataclass
class OfferCompletedEvent(CMSEvent):
    event_type: str = 'offer_completed'
    user_id: Optional[int] = None
    payout_usd: float = 0.0
    lead_id: str = ''
    campaign_id: str = ''
    virtual_amount: float = 0.0


@dataclass
class ContentLockedEvent(CMSEvent):
    event_type: str = 'content_locked'
    user_id: Optional[int] = None
    locker_id: int = 0
    locker_type: str = ''


@dataclass
class ContentUnlockedEvent(CMSEvent):
    event_type: str = 'content_unlocked'
    user_id: Optional[int] = None
    locker_id: int = 0


# ══════════════════════════════════════════════════════════════════════════════
# Survey events
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SurveyStartedEvent(CMSEvent):
    event_type: str = 'survey_started'
    user_id: Optional[int] = None
    survey_id: str = ''
    completion_id: str = ''
    started_at: str = ''


@dataclass
class SurveyCompletedEvent(CMSEvent):
    event_type: str = 'survey_completed'
    user_id: Optional[int] = None
    survey_id: str = ''
    completion_id: str = ''
    quality_score: float = 0.0
    completed_at: str = ''


@dataclass
class SurveyResponseSubmittedEvent(CMSEvent):
    event_type: str = 'survey_response_submitted'
    user_id: Optional[int] = None
    survey_id: str = ''
    completion_id: str = ''
    response_count: int = 0
    submitted_at: str = ''


@dataclass
class SurveyQualityUpdatedEvent(CMSEvent):
    event_type: str = 'survey_quality_updated'
    completion_id: str = ''
    old_quality: float = 0.0
    new_quality: float = 0.0
    updated_at: str = ''


@dataclass
class SurveyCreatedEvent(CMSEvent):
    event_type: str = 'survey_created'
    created_by: Optional[int] = None
    survey_id: str = ''
    title: str = ''
    created_at: str = ''


@dataclass
class SurveyUpdatedEvent(CMSEvent):
    event_type: str = 'survey_updated'
    survey_id: str = ''
    updated_by: Optional[int] = None
    changed_fields: list = field(default_factory=list)
    updated_at: str = ''


@dataclass
class SurveyDeletedEvent(CMSEvent):
    event_type: str = 'survey_deleted'
    survey_id: str = ''
    deleted_by: Optional[int] = None
    deleted_at: str = ''


# ══════════════════════════════════════════════════════════════════════════════
# Task Management events
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TaskStartedEvent(CMSEvent):
    event_type: str = 'task_started'
    task_id: str = ''
    execution_id: str = ''
    worker_id: str = ''
    started_at: str = ''


@dataclass
class TaskCompletedEvent(CMSEvent):
    event_type: str = 'task_completed'
    task_id: str = ''
    execution_id: str = ''
    runtime_seconds: float = 0.0
    success: bool = False
    completed_at: str = ''


@dataclass
class TaskFailedEvent(CMSEvent):
    event_type: str = 'task_failed'
    task_id: str = ''
    execution_id: str = ''
    error_message: str = ''
    retry_count: int = 0
    failed_at: str = ''


@dataclass
class TaskScheduledEvent(CMSEvent):
    event_type: str = 'task_scheduled'
    task_id: str = ''
    next_run_time: str = ''
    created_by: Optional[int] = None
    scheduled_at: str = ''


@dataclass
class TaskQueueUpdatedEvent(CMSEvent):
    event_type: str = 'task_queue_updated'
    queue_item_id: str = ''
    old_status: str = ''
    new_status: str = ''
    updated_at: str = ''


@dataclass
class TaskTimeoutEvent(CMSEvent):
    event_type: str = 'task_timeout'
    task_id: str = ''
    execution_id: str = ''
    timeout_duration: float = 0.0
    timed_out_at: str = ''


# ══════════════════════════════════════════════════════════════════════════════
# User Profile events
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ProfileUpdatedEvent(CMSEvent):
    event_type: str = 'profile_updated'
    user_id: Optional[int] = None
    profile_id: str = ''
    changed_fields: list = field(default_factory=list)
    updated_at: str = ''


@dataclass
class ProfileCompletenessChangedEvent(CMSEvent):
    event_type: str = 'profile_completeness_changed'
    user_id: Optional[int] = None
    profile_id: str = ''
    old_completeness: float = 0.0
    new_completeness: float = 0.0
    changed_at: str = ''


@dataclass
class UserSegmentChangedEvent(CMSEvent):
    event_type: str = 'user_segment_changed'
    user_id: Optional[int] = None
    old_segments: list = field(default_factory=list)
    new_segments: list = field(default_factory=list)
    changed_at: str = ''


@dataclass
class UserRegisteredEvent(CMSEvent):
    event_type: str = 'user_registered'
    user_id: Optional[int] = None
    registration_method: str = ''
    registered_at: str = ''


@dataclass
class UserLoginEvent(CMSEvent):
    event_type: str = 'user_login'
    user_id: Optional[int] = None
    login_method: str = ''
    ip_address: str = ''
    user_agent: str = ''
    logged_in_at: str = ''


@dataclass
class UserLogoutEvent(CMSEvent):
    event_type: str = 'user_logout'
    user_id: Optional[int] = None
    logout_reason: str = ''
    logged_out_at: str = ''


# ══════════════════════════════════════════════════════════════════════════════
# Analytics events
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class AnalyticsUpdatedEvent(CMSEvent):
    event_type: str = 'analytics_updated'
    data_type: str = ''
    instance_id: str = ''
    old_data: dict = field(default_factory=dict)
    new_data: dict = field(default_factory=dict)
    updated_at: str = ''


@dataclass
class ReportGeneratedEvent(CMSEvent):
    event_type: str = 'report_generated'
    report_type: str = ''
    file_path: str = ''
    generated_by: Optional[int] = None
    filters: dict = field(default_factory=dict)
    generated_at: str = ''


@dataclass
class DashboardDataUpdatedEvent(CMSEvent):
    event_type: str = 'dashboard_data_updated'
    user_id: Optional[int] = None
    section: str = ''
    data: dict = field(default_factory=dict)
    updated_at: str = ''


@dataclass
class MetricsCollectedEvent(CMSEvent):
    event_type: str = 'metrics_collected'
    metric_type: str = ''
    value: float = 0.0
    tags: dict = field(default_factory=dict)
    collected_at: str = ''


# ══════════════════════════════════════════════════════════════════════════════
# Notification events
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class NotificationCreatedEvent(CMSEvent):
    event_type: str = 'notification_created'
    user_id: Optional[int] = None
    notification_id: str = ''
    recipients: list = field(default_factory=list)
    created_at: str = ''


@dataclass
class NotificationReadEvent(CMSEvent):
    event_type: str = 'notification_read'
    user_id: Optional[int] = None
    notification_id: str = ''
    read_at: str = ''


@dataclass
class BulkNotificationSentEvent(CMSEvent):
    event_type: str = 'bulk_notification_sent'
    recipients: list = field(default_factory=list)
    notification_data: dict = field(default_factory=dict)
    sent_count: int = 0
    sent_at: str = ''


# ══════════════════════════════════════════════════════════════════════════════
# System events
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SystemMaintenanceStartedEvent(CMSEvent):
    event_type: str = 'system_maintenance_started'
    reason: str = ''
    estimated_duration: int = 0
    affected_services: list = field(default_factory=list)
    started_at: str = ''


@dataclass
class SystemMaintenanceEndedEvent(CMSEvent):
    event_type: str = 'system_maintenance_ended'
    duration: int = 0
    affected_services: list = field(default_factory=list)
    ended_at: str = ''


@dataclass
class CacheInvalidatedEvent(CMSEvent):
    event_type: str = 'cache_invalidated'
    cache_key: str = ''
    pattern: str = ''
    invalidated_by: str = ''
    invalidated_at: str = ''


@dataclass
class WebhookTriggeredEvent(CMSEvent):
    event_type: str = 'webhook_triggered'
    webhook_url: str = ''
    event_type_webhook: str = ''
    payload: dict = field(default_factory=dict)
    response_status: int = 0
    triggered_at: str = ''


@dataclass
class ErrorOccurredEvent(CMSEvent):
    event_type: str = 'error_occurred'
    error_type: str = ''
    error_message: str = ''
    context: dict = field(default_factory=dict)
    severity: str = 'error'
    occurred_at: str = ''


@dataclass
class PerformanceAlertEvent(CMSEvent):
    event_type: str = 'performance_alert'
    metric_name: str = ''
    threshold: float = 0.0
    actual_value: float = 0.0
    alert_type: str = ''
    triggered_at: str = ''
    locker_type: str = ''
    lead_id: str = ''


# ══════════════════════════════════════════════════════════════════════════════
# Game / progression events
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class UserLevelUpEvent(CMSEvent):
    event_type: str = 'user_level_up'
    user_id: Optional[int] = None
    old_level: int = 0
    new_level: int = 0


@dataclass
class WithdrawalRequestedEvent(CMSEvent):
    event_type: str = 'withdrawal_requested'
    user_id: Optional[int] = None
    amount_coins: float = 0.0
    amount_usd: float = 0.0
    method: str = ''
    request_id: int = 0


@dataclass
class QuizCompletedEvent(CMSEvent):
    event_type: str = 'quiz_completed'
    user_id: Optional[int] = None
    quiz_id: int = 0
    attempt_id: int = 0
    reward_coins: float = 0.0
    result_title: str = ''


@dataclass
class ReferralBonusEvent(CMSEvent):
    event_type: str = 'referral_bonus'
    referrer_id: Optional[int] = None
    referred_id: Optional[int] = None
    bonus_usd: float = 0.0
    bonus_coins: float = 0.0
    lead_id: str = ''


@dataclass
class StreakMilestoneEvent(CMSEvent):
    event_type: str = 'streak_milestone'
    user_id: Optional[int] = None
    streak_days: int = 0
    bonus_coins: float = 0.0
    milestone_title: str = ''


@dataclass
class BlogPostPublishedEvent(CMSEvent):
    event_type: str = 'blog_post_published'
    post_id: int = 0
    author_id: Optional[int] = None
    title: str = ''
    slug: str = ''


# ══════════════════════════════════════════════════════════════════════════════
# Core publish_event() — unchanged from original
# ══════════════════════════════════════════════════════════════════════════════

def publish_event(event: CMSEvent) -> None:
    """
    Publish a typed event to the EventBus.
    Silent on failure — never raises to caller.
    """
    try:
        from api.cms.INTEGRATION_SYSTEM.event_bus import EventBus
        import dataclasses
        EventBus.publish(event.event_type, dataclasses.asdict(event))
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# fire_*() convenience functions — NEW (FIX)
#
# These one-liner helpers are what services should call.
# They handle dataclass construction + publish_event() in one call.
# All are silent on error (fire-and-forget pattern).
# ══════════════════════════════════════════════════════════════════════════════

def fire_reward_earned(user, amount: float, source_type: str,
                       lead_id: str = '', virtual_amount: float = 0.0,
                       currency: str = 'USD', transaction_id: str = '') -> None:
    """
    Fire after a reward is credited.
    Usage (in CPALeadService.handle_postback):
        from api.cms.events import fire_reward_earned
        fire_reward_earned(user=user, amount=payout_usd,
                           source_type='cpalead', lead_id=lead_id)
    """
    publish_event(RewardEarnedEvent(
        user_id=getattr(user, 'id', None),
        amount=float(amount),
        currency=currency,
        source_type=source_type,
        lead_id=lead_id,
        virtual_amount=float(virtual_amount),
        transaction_id=transaction_id,
        earned_at=timezone.now().isoformat(),
    ))


def fire_reward_approved(user, transaction_id: str, amount: float,
                         approved_by=None) -> None:
    publish_event(RewardApprovedEvent(
        user_id=getattr(user, 'id', None),
        transaction_id=transaction_id,
        amount=float(amount),
        approved_by=getattr(approved_by, 'id', None),
        approved_at=timezone.now().isoformat(),
    ))


def fire_reward_paid(user, transaction_id: str, amount: float,
                     payment_method: str = '') -> None:
    publish_event(RewardPaidEvent(
        user_id=getattr(user, 'id', None),
        transaction_id=transaction_id,
        amount=float(amount),
        payment_method=payment_method,
        paid_at=timezone.now().isoformat(),
    ))


def fire_offer_completed(user, payout_usd: float, lead_id: str,
                          virtual_amount: float = 0.0) -> None:
    """
    Fire after CPAlead postback is approved.
    Usage (in CPALeadService.handle_postback):
        from api.cms.events import fire_offer_completed
        fire_offer_completed(user=user, payout_usd=payout, lead_id=lead_id)
    """
    publish_event(OfferCompletedEvent(
        user_id=getattr(user, 'id', None),
        payout_usd=float(payout_usd),
        lead_id=lead_id,
        virtual_amount=float(virtual_amount),
    ))


def fire_survey_started(user, survey_id: str, completion_id: str = '') -> None:
    """
    Fire when a user begins a survey.
    Usage (in ProfileSurveyService.start_survey):
        from api.cms.events import fire_survey_started
        fire_survey_started(user=user, survey_id=str(survey.id))
    """
    publish_event(SurveyStartedEvent(
        user_id=getattr(user, 'id', None),
        survey_id=survey_id,
        completion_id=completion_id,
        started_at=timezone.now().isoformat(),
    ))


def fire_survey_completed(user, survey_id: str, completion_id: str = '',
                           quality_score: float = 0.0) -> None:
    """
    Fire when a survey is fully completed and reward is ready.
    Usage (in ProfileSurveyService.complete_survey):
        from api.cms.events import fire_survey_completed
        fire_survey_completed(user=user, survey_id=str(survey.id),
                               completion_id=str(completion.id),
                               quality_score=quality)
    """
    publish_event(SurveyCompletedEvent(
        user_id=getattr(user, 'id', None),
        survey_id=survey_id,
        completion_id=completion_id,
        quality_score=float(quality_score),
        completed_at=timezone.now().isoformat(),
    ))


def fire_survey_response_submitted(user, survey_id: str, completion_id: str,
                                    response_count: int = 0) -> None:
    publish_event(SurveyResponseSubmittedEvent(
        user_id=getattr(user, 'id', None),
        survey_id=survey_id,
        completion_id=completion_id,
        response_count=response_count,
        submitted_at=timezone.now().isoformat(),
    ))


def fire_withdrawal_requested(user, amount_coins: float, amount_usd: float,
                               method: str, request_id: int = 0) -> None:
    """
    Fire after WithdrawalService creates a new pending request.
    Usage (in WithdrawalService.create_withdrawal_request):
        from api.cms.events import fire_withdrawal_requested
        fire_withdrawal_requested(user=user, amount_coins=coins,
                                   amount_usd=float(amount), method=method,
                                   request_id=wr.pk)
    """
    publish_event(WithdrawalRequestedEvent(
        user_id=getattr(user, 'id', None),
        amount_coins=float(amount_coins),
        amount_usd=float(amount_usd),
        method=method,
        request_id=request_id,
    ))


def fire_user_level_up(user, old_level: int, new_level: int) -> None:
    publish_event(UserLevelUpEvent(
        user_id=getattr(user, 'id', None),
        old_level=old_level,
        new_level=new_level,
    ))


def fire_quiz_completed(user, quiz_id: int, attempt_id: int,
                         reward_coins: float = 0.0, result_title: str = '') -> None:
    publish_event(QuizCompletedEvent(
        user_id=getattr(user, 'id', None),
        quiz_id=quiz_id,
        attempt_id=attempt_id,
        reward_coins=float(reward_coins),
        result_title=result_title,
    ))


def fire_referral_bonus(referrer, referred, bonus_usd: float = 0.0,
                         bonus_coins: float = 0.0, lead_id: str = '') -> None:
    publish_event(ReferralBonusEvent(
        referrer_id=getattr(referrer, 'id', None),
        referred_id=getattr(referred, 'id', None),
        bonus_usd=float(bonus_usd),
        bonus_coins=float(bonus_coins),
        lead_id=lead_id,
    ))


def fire_streak_milestone(user, streak_days: int, bonus_coins: float = 0.0,
                           milestone_title: str = '') -> None:
    publish_event(StreakMilestoneEvent(
        user_id=getattr(user, 'id', None),
        streak_days=streak_days,
        bonus_coins=float(bonus_coins),
        milestone_title=milestone_title,
    ))


def fire_blog_post_published(post_id: int, author=None,
                              title: str = '', slug: str = '') -> None:
    publish_event(BlogPostPublishedEvent(
        post_id=post_id,
        author_id=getattr(author, 'id', None),
        title=title,
        slug=slug,
    ))


def fire_task_started(task_id: str, execution_id: str = '',
                       worker_id: str = '') -> None:
    publish_event(TaskStartedEvent(
        task_id=task_id,
        execution_id=execution_id,
        worker_id=worker_id,
        started_at=timezone.now().isoformat(),
    ))


def fire_task_completed(task_id: str, execution_id: str = '',
                         runtime_seconds: float = 0.0, success: bool = True) -> None:
    publish_event(TaskCompletedEvent(
        task_id=task_id,
        execution_id=execution_id,
        runtime_seconds=runtime_seconds,
        success=success,
        completed_at=timezone.now().isoformat(),
    ))


def fire_task_failed(task_id: str, execution_id: str = '',
                      error_message: str = '', retry_count: int = 0) -> None:
    publish_event(TaskFailedEvent(
        task_id=task_id,
        execution_id=execution_id,
        error_message=error_message,
        retry_count=retry_count,
        failed_at=timezone.now().isoformat(),
    ))


def fire_profile_updated(user, profile_id: str = '',
                          changed_fields: Optional[List[str]] = None) -> None:
    publish_event(ProfileUpdatedEvent(
        user_id=getattr(user, 'id', None),
        profile_id=profile_id,
        changed_fields=changed_fields or [],
        updated_at=timezone.now().isoformat(),
    ))


def fire_user_registered(user, registration_method: str = 'email') -> None:
    publish_event(UserRegisteredEvent(
        user_id=getattr(user, 'id', None),
        registration_method=registration_method,
        registered_at=timezone.now().isoformat(),
    ))


def fire_user_login(user, ip_address: str = '', user_agent: str = '',
                    login_method: str = 'password') -> None:
    publish_event(UserLoginEvent(
        user_id=getattr(user, 'id', None),
        login_method=login_method,
        ip_address=ip_address,
        user_agent=user_agent,
        logged_in_at=timezone.now().isoformat(),
    ))


def fire_reward_pool_low(pool_id: str, pool_name: str,
                          utilization_percentage: float,
                          remaining_amount: float) -> None:
    publish_event(RewardPoolLowEvent(
        pool_id=pool_id,
        pool_name=pool_name,
        utilization_percentage=float(utilization_percentage),
        remaining_amount=float(remaining_amount),
        alert_at=timezone.now().isoformat(),
    ))


def fire_cache_invalidated(cache_key: str = '', pattern: str = '',
                            invalidated_by: str = 'system') -> None:
    publish_event(CacheInvalidatedEvent(
        cache_key=cache_key,
        pattern=pattern,
        invalidated_by=invalidated_by,
        invalidated_at=timezone.now().isoformat(),
    ))


def fire_error_occurred(error_type: str, error_message: str,
                         context: Optional[dict] = None,
                         severity: str = 'error') -> None:
    publish_event(ErrorOccurredEvent(
        error_type=error_type,
        error_message=error_message,
        context=context or {},
        severity=severity,
        occurred_at=timezone.now().isoformat(),
    ))
