# api/cms/receivers.py
"""Django signal receivers — all CMS signal handlers in one place."""
import logging
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile_on_register(sender, instance, created, **kwargs):
    """Auto-create UserProfile + ReferralCode on new user registration."""
    if not created:
        return
    try:
        from api.cms.models_new.withdrawal import UserProfile
        UserProfile.objects.get_or_create(user=instance)
    except Exception as e:
        logger.warning(f"[Receiver] UserProfile create failed: {e}")
    try:
        from api.cms.models_new.referral import ReferralCode
        ReferralCode.get_or_create_for_user(instance)
    except Exception as e:
        logger.warning(f"[Receiver] ReferralCode create failed: {e}")


@receiver(post_save, sender=User)
def create_virtual_balance_on_register(sender, instance, created, **kwargs):
    """Auto-create virtual balance for new users."""
    if not created:
        return
    try:
        from api.cms.models_new.cpalead import VirtualCurrency, UserVirtualBalance
        vc = VirtualCurrency.get_active()
        if vc:
            UserVirtualBalance.objects.get_or_create(
                user=instance,
                defaults={'currency': vc, 'balance': 0}
            )
    except Exception as e:
        logger.warning(f"[Receiver] VirtualBalance create failed: {e}")


def _on_reward_earned(sender, user, amount, currency, source_type,
                       lead_id='', virtual_amount=0, **kwargs):
    """Update UserProfile totals when reward is earned."""
    if not user:
        return


# ── Survey Signal Receivers ───────────────────────────────────────

@receiver(post_save, sender='api_cms.SurveyCompletion')
def on_survey_completion(sender, instance, created, **kwargs):
    """Handle survey completion events."""
    if not created:
        return
    
    try:
        from .services_new.SurveyRewardService import SurveyRewardService
        service = SurveyRewardService()
        service.process_completion_reward(instance.user, instance)
    except Exception as e:
        logger.error(f"[Receiver] Survey completion reward processing failed: {e}")
    
    try:
        from .services_new.UserProfileService import UserProfileService
        profile_service = UserProfileService()
        profile_service.update_participation_score(instance.user)
    except Exception as e:
        logger.error(f"[Receiver] Profile participation score update failed: {e}")


@receiver(post_save, sender='api_cms.SurveyTemplate')
def on_survey_created(sender, instance, created, **kwargs):
    """Handle survey creation events."""
    if not created:
        return
    
    try:
        from .services_new.UserSegmentService import UserSegmentService
        segment_service = UserSegmentService()
        segment_service.update_survey_recommendations_for_segments(instance)
    except Exception as e:
        logger.error(f"[Receiver] Survey segment update failed: {e}")


# ── Reward Signal Receivers ─────────────────────────────────────

@receiver(post_save, sender='api_cms.RewardTransaction')
def on_reward_transaction_created(sender, instance, created, **kwargs):
    """Handle reward transaction events."""
    if not created:
        return
    
    try:
        from .services_new.UserProfileService import UserProfileService
        profile_service = UserProfileService()
        profile_service.update_reward_totals(instance.user)
    except Exception as e:
        logger.error(f"[Receiver] Reward totals update failed: {e}")
    
    # Send notification for approved transactions
    if instance.status == 'approved':
        try:
            from .services_new.NotificationService import NotificationService
            notification_service = NotificationService()
            notification_service.send_notification(
                instance.user,
                {
                    'type': 'reward_approved',
                    'title': 'Reward Approved',
                    'message': f'Your reward of ${instance.amount} has been approved.',
                    'data': {
                        'transaction_id': str(instance.uuid),
                        'amount': float(instance.amount)
                    }
                }
            )
        except Exception as e:
            logger.error(f"[Receiver] Reward notification failed: {e}")


@receiver(post_save, sender='api_cms.RewardPool')
def on_reward_pool_updated(sender, instance, **kwargs):
    """Handle reward pool updates."""
    try:
        from .services_new.SurveyRewardService import SurveyRewardService
        service = SurveyRewardService()
        
        # Check if pool needs refill
        if service.should_auto_refill_pool(instance):
            service.auto_refill_pool(instance)
        
        # Check if pool is running low
        if service.is_pool_low(instance):
            from .services_new.NotificationService import NotificationService
            notification_service = NotificationService()
            notification_service.send_bulk_notifications(
                instance.get_admin_users(),
                {
                    'type': 'pool_low',
                    'title': 'Reward Pool Low',
                    'message': f'Reward pool "{instance.name}" is running low on funds.',
                    'data': {
                        'pool_id': str(instance.uuid),
                        'pool_name': instance.name,
                        'utilization': service.get_pool_utilization(instance)
                    }
                }
            )
    except Exception as e:
        logger.error(f"[Receiver] Reward pool update failed: {e}")


# ── Task Management Signal Receivers ───────────────────────────────

@receiver(post_save, sender='api_cms.TaskExecution')
def on_task_execution_completed(sender, instance, created, **kwargs):
    """Handle task execution events."""
    if not created:
        return
    
    # Send notifications for failed tasks
    if instance.status == 'failure':
        try:
            from .services_new.NotificationService import NotificationService
            notification_service = NotificationService()
            notification_service.send_bulk_notifications(
                instance.get_admin_users(),
                {
                    'type': 'task_failed',
                    'title': 'Task Failed',
                    'message': f'Task "{instance.schedule.task_name}" failed to execute.',
                    'data': {
                        'task_id': str(instance.uuid),
                        'task_name': instance.schedule.task_name,
                        'error_message': instance.error_message,
                        'runtime_seconds': instance.runtime_seconds
                    }
                }
            )
        except Exception as e:
            logger.error(f"[Receiver] Task failure notification failed: {e}")
    
    # Update task schedule next run time
    if instance.status == 'success':
        try:
            from .services_new.TaskManagementService import TaskManagementService
            task_service = TaskManagementService()
            task_service.update_next_run_time(instance.schedule)
        except Exception as e:
            logger.error(f"[Receiver] Task next run update failed: {e}")


@receiver(post_save, sender='api_cms.TaskSchedule')
def on_task_schedule_created(sender, instance, created, **kwargs):
    """Handle task schedule creation."""
    if not created:
        return
    
    try:
        from .services_new.TaskManagementService import TaskManagementService
        task_service = TaskManagementService()
        
        # Validate cron expression
        if instance.cron_expression:
            task_service.validate_cron_expression(instance.cron_expression)
        
        # Schedule initial execution
        task_service.schedule_initial_execution(instance)
    except Exception as e:
        logger.error(f"[Receiver] Task schedule setup failed: {e}")


# ── User Profile Signal Receivers ───────────────────────────────────

@receiver(post_save, sender='api_cms.UserProfile')
def on_user_profile_updated(sender, instance, **kwargs):
    """Handle user profile updates."""
    try:
        from .services_new.UserSegmentService import UserSegmentService
        segment_service = UserSegmentService()
        segment_service.update_user_segments(instance.user)
    except Exception as e:
        logger.error(f"[Receiver] User segment update failed: {e}")
    
    # Update survey recommendations based on new profile
    try:
        from .services_new.ProfileSurveyService import ProfileSurveyManager
        manager = ProfileSurveyManager()
        manager.update_survey_recommendations(instance.user)
    except Exception as e:
        logger.error(f"[Receiver] Survey recommendation update failed: {e}")


# ── System Signal Receivers ───────────────────────────────────────

@receiver(post_save, sender='api_cms.Notification')
def on_notification_created(sender, instance, created, **kwargs):
    """Handle notification creation for real-time updates."""
    if not created:
        return
    
    try:
        from .channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"cms_notifications_{instance.user.id}",
            {
                'type': 'notification',
                'data': {
                    'id': str(instance.uuid),
                    'title': instance.title,
                    'message': instance.message,
                    'created_at': instance.created_at.isoformat(),
                    'read': instance.read
                }
            }
        )
    except Exception as e:
        logger.error(f"[Receiver] WebSocket notification failed: {e}")


# ── Cleanup Signal Receivers ───────────────────────────────────────

@receiver(post_delete, sender='api_cms.SurveyTemplate')
def on_survey_deleted(sender, instance, **kwargs):
    """Cleanup related data when survey is deleted."""
    try:
        from .services_new.SurveyAnalyticsService import SurveyAnalyticsService
        analytics_service = SurveyAnalyticsService()
        analytics_service.cleanup_survey_data(instance)
    except Exception as e:
        logger.error(f"[Receiver] Survey cleanup failed: {e}")


@receiver(post_delete, sender='api_cms.UserProfile')
def on_user_profile_deleted(sender, instance, **kwargs):
    """Cleanup related data when user profile is deleted."""
    try:
        from .services_new.UserSegmentService import UserSegmentService
        segment_service = UserSegmentService()
        segment_service.remove_user_from_all_segments(instance.user)
    except Exception as e:
        logger.error(f"[Receiver] User profile cleanup failed: {e}")
    try:
        from api.cms.models_new.withdrawal import UserProfile
        from django.db.models import F
        from decimal import Decimal
        usd = Decimal(str(amount)) if currency == 'USD' else Decimal('0')
        coins = Decimal(str(virtual_amount)) if virtual_amount else Decimal('0')
        UserProfile.objects.filter(user=user).update(
            total_earned_usd=F('total_earned_usd') + usd,
            total_earned_coins=F('total_earned_coins') + coins,
        )
    except Exception as e:
        logger.debug(f"[Receiver] UserProfile total update failed: {e}")

    # Also update leaderboard score
    try:
        from api.cms.services_new.LeaderboardService import LeaderboardService, StreakService
        from decimal import Decimal
        if amount:
            LeaderboardService.update_score(user, Decimal(str(amount)), 'earnings', 'weekly')
            LeaderboardService.update_score(user, Decimal(str(amount)), 'earnings', 'monthly')
        if virtual_amount:
            LeaderboardService.update_score(user, Decimal(str(virtual_amount)), 'coins', 'weekly')
        StreakService.record_earn(user)
    except Exception as e:
        logger.debug(f"[Receiver] Leaderboard update failed: {e}")

    # Award referral bonus
    if lead_id:
        try:
            from api.cms.services_new.ReferralService import ReferralService
            from decimal import Decimal
            ReferralService.award_referral_bonus(
                referred_user=user,
                original_amount_usd=Decimal(str(amount)) if currency == 'USD' else Decimal('0'),
                source='offer_complete',
                lead_id=lead_id,
            )
        except Exception as e:
            logger.debug(f"[Receiver] Referral bonus failed: {e}")


def _on_offer_completed(sender, user, payout_usd, lead_id, virtual_amount=0, **kwargs):
    """Update user offer count when CPAlead offer is completed."""
    if not user:
        return
    try:
        from api.cms.models_new.withdrawal import UserProfile
        from django.db.models import F
        UserProfile.objects.filter(user=user).update(
            total_offers_completed=F('total_offers_completed') + 1
        )
    except Exception as e:
        logger.debug(f"[Receiver] Offer count update failed: {e}")

    # Auto-level update
    try:
        from api.cms.services_new.WithdrawalService import UserProfileService
        new_level = UserProfileService.update_level(user)
    except Exception as e:
        logger.debug(f"[Receiver] Level update failed: {e}")


def connect_receivers():
    """Connect all signal receivers. Called from apps.py ready()."""
    try:
        from api.cms.INTEGRATION_SYSTEM.integ_signals import (
            cms_reward_earned, cms_offer_completed
        )
        cms_reward_earned.connect(_on_reward_earned, dispatch_uid="cms_receiver_reward_earned")
        cms_offer_completed.connect(_on_offer_completed, dispatch_uid="cms_receiver_offer_completed")
        logger.info("[Receivers] CMS signal receivers connected")
    except ImportError:
        logger.debug("[Receivers] INTEGRATION_SYSTEM not available — skipping")


# =============================================================================
# INTERACTOR INTEGRATION — v9 PRODUCTION FIX
# -----------------------------------------------------------------------------
# interactors.py defined PostbackProcessingInteractor, WithdrawalApprovalInteractor,
# UserOnboardingInteractor, SurveyInteractionInteractor — but they were NEVER
# connected to any Django signal or called from any view.
#
# This section wires each interactor into the appropriate signal so that
# ALL business side-effects (coin award + referral + streak + level + push)
# fire automatically on every key event.
# =============================================================================

def _on_new_user_registered_interactor(sender, instance, created, **kwargs):
    """
    When a new User is saved: run UserOnboardingInteractor for side-effects.
    Handles: VirtualBalance creation, ReferralCode setup, welcome bonus,
             welcome push, user_registered event.
    Only runs for fresh users (created=True) AND only if the base receivers
    above have already run (so we don't double-create UserProfile).
    """
    if not created:
        return
    try:
        from api.cms.interactors import UserOnboardingInteractor
        interactor = UserOnboardingInteractor()
        interactor._post_registration_side_effects(user=instance)
    except Exception as e:
        logger.debug(f'[Receiver:Interactor] post-registration side-effects skipped: {e}')


def _on_postback_via_interactor(sender, user, payout_usd, lead_id,
                                  virtual_amount=0, offer_id='',
                                  ip='', **kwargs):
    """
    When cpalead_postback_approved fires: run PostbackProcessingInteractor
    for FULL side-effects (referral bonus + streak + level-up + push).
    """
    try:
        from api.cms.interactors import PostbackProcessingInteractor
        interactor = PostbackProcessingInteractor()
        interactor._post_award_effects(
            user=user,
            payout_usd=payout_usd,
            coins=virtual_amount,
            lead_id=lead_id,
        )
    except Exception as e:
        logger.debug(f'[Receiver:Interactor] postback side-effects skipped: {e}')


def _on_survey_completed_interactor(sender, user, survey_id, completion_id,
                                     quality_score=0, reward_usd=0, **kwargs):
    """
    When cms_survey_completed fires: trigger SurveyInteractionInteractor
    for streak update, level check, push notification.
    """
    try:
        from api.cms.interactors import SurveyInteractionInteractor
        interactor = SurveyInteractionInteractor()
        interactor._post_completion_effects(
            user=user,
            completion_id=completion_id,
            quality_score=quality_score,
            reward_usd=reward_usd,
        )
    except Exception as e:
        logger.debug(f'[Receiver:Interactor] survey side-effects skipped: {e}')


def connect_interactor_receivers():
    """
    Wire all interactor receivers to their Django signals.
    Called from connect_receivers() which is called from apps.py.ready().
    """
    # New user registration → onboarding side-effects
    User_ = get_user_model()
    post_save.connect(
        _on_new_user_registered_interactor,
        sender=User_,
        dispatch_uid='interactor_onboarding_side_effects',
    )

    # CPAlead postback approved → full interactor side-effects
    try:
        from api.cms.INTEGRATION_SYSTEM.integ_signals import cpalead_postback_approved
        cpalead_postback_approved.connect(
            _on_postback_via_interactor,
            dispatch_uid='interactor_postback_side_effects',
        )
    except ImportError:
        pass

    # Survey completed → interactor side-effects
    try:
        from api.cms.INTEGRATION_SYSTEM.integ_signals import cms_survey_completed
        cms_survey_completed.connect(
            _on_survey_completed_interactor,
            dispatch_uid='interactor_survey_side_effects',
        )
    except ImportError:
        pass

    logger.info('[Receivers] Interactor receivers connected.')


# Patch connect_receivers to also call connect_interactor_receivers
_original_connect_receivers = connect_receivers


def connect_receivers():
    """
    Extended connect_receivers: runs all original receivers + interactor receivers.
    Overwrites the original function so apps.py.ready() calls this version.
    """
    _original_connect_receivers()
    try:
        connect_interactor_receivers()
    except Exception as e:
        logger.warning(f'[Receivers] Interactor wiring failed: {e}')
