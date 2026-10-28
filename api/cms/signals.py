# api/cms/signals.py
"""
Production-ready signals for api.cms.
Handles: cache invalidation, notification creation, analytics updates.
"""
import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# ── ContentPage signals ───────────────────────────────────────────

@receiver(post_save, sender='cms.ContentPage')
def content_page_saved(sender, instance, created, **kwargs):
    """Invalidate caches when a content page is saved."""
    try:
        from api.cms.services_new.CMSCacheService import CMSCacheService
        CMSCacheService.invalidate_content_page(instance)
        if instance.status == 'published':
            # Update sitemap
            from api.cms.services_new.SEOService import SEOService
            try:
                SEOService.add_url_to_sitemap(
                    url=instance.get_absolute_url(),
                    changefreq='weekly',
                    priority=0.8
                )
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"ContentPage post_save signal error (non-critical): {e}")


@receiver(post_delete, sender='cms.ContentPage')
def content_page_deleted(sender, instance, **kwargs):
    """Clean up caches when content page is deleted."""
    try:
        from api.cms.services_new.CMSCacheService import CMSCacheService
        CMSCacheService.invalidate_content_page(instance)
    except Exception:
        pass


# ── BlogPost signals ──────────────────────────────────────────────

@receiver(post_save, sender='cms.BlogPost')
def blog_post_saved(sender, instance, created, **kwargs):
    """Invalidate blog caches on save."""
    try:
        from api.cms.services_new.CMSCacheService import CMSCacheService
        CMSCacheService.invalidate_blog_post(instance)
        if instance.status == 'published' and instance.category:
            from api.cms.models_new.blog import BlogCategory
            BlogCategory.objects.filter(id=instance.category.id).update(
                post_count=BlogCategory.objects.filter(
                    id=instance.category.id
                ).annotate(
                    cnt=__import__('django.db.models', fromlist=['Count']).Count(
                        'blog_posts',
                        filter=__import__('django.db.models', fromlist=['Q']).Q(
                            blog_posts__status='published', blog_posts__is_active=True
                        )
                    )
                ).values('cnt').first()['cnt']
            )
    except Exception as e:
        logger.debug(f"BlogPost signal error (non-critical): {e}")


# ── Survey Signals ─────────────────────────────────────────────

survey_completed = None
survey_started = None
survey_response_submitted = None
survey_quality_updated = None

def get_survey_completed_signal():
    """Get or create the survey_completed signal."""
    global survey_completed
    if survey_completed is None:
        from django.dispatch import Signal
        survey_completed = Signal(
        )
    return survey_completed

def get_survey_started_signal():
    """Get or create the survey_started signal."""
    global survey_started
    if survey_started is None:
        from django.dispatch import Signal
        survey_started = Signal(
        )
    return survey_started

def get_survey_response_submitted_signal():
    """Get or create the survey_response_submitted signal."""
    global survey_response_submitted
    if survey_response_submitted is None:
        from django.dispatch import Signal
        survey_response_submitted = Signal(
        )
    return survey_response_submitted

def get_survey_quality_updated_signal():
    """Get or create the survey_quality_updated signal."""
    global survey_quality_updated
    if survey_quality_updated is None:
        from django.dispatch import Signal
        survey_quality_updated = Signal(
        )
    return survey_quality_updated


# ── Reward Signals ─────────────────────────────────────────────

reward_earned = None
reward_approved = None
reward_paid = None
reward_pool_low = None
reward_pool_refilled = None

def get_reward_earned_signal():
    """Get or create the reward_earned signal."""
    global reward_earned
    if reward_earned is None:
        from django.dispatch import Signal
        reward_earned = Signal(
        )
    return reward_earned

def get_reward_approved_signal():
    """Get or create the reward_approved signal."""
    global reward_approved
    if reward_approved is None:
        from django.dispatch import Signal
        reward_approved = Signal(
        )
    return reward_approved

def get_reward_paid_signal():
    """Get or create the reward_paid signal."""
    global reward_paid
    if reward_paid is None:
        from django.dispatch import Signal
        reward_paid = Signal(
        )
    return reward_paid

def get_reward_pool_low_signal():
    """Get or create the reward_pool_low signal."""
    global reward_pool_low
    if reward_pool_low is None:
        from django.dispatch import Signal
        reward_pool_low = Signal(
        )
    return reward_pool_low

def get_reward_pool_refilled_signal():
    """Get or create the reward_pool_refilled signal."""
    global reward_pool_refilled
    if reward_pool_refilled is None:
        from django.dispatch import Signal
        reward_pool_refilled = Signal(
        )
    return reward_pool_refilled


# ── Task Management Signals ─────────────────────────────────────

task_started = None
task_completed = None
task_failed = None
task_scheduled = None
task_queue_updated = None

def get_task_started_signal():
    """Get or create the task_started signal."""
    global task_started
    if task_started is None:
        from django.dispatch import Signal
        task_started = Signal(
        )
    return task_started

def get_task_completed_signal():
    """Get or create the task_completed signal."""
    global task_completed
    if task_completed is None:
        from django.dispatch import Signal
        task_completed = Signal(
        )
    return task_completed

def get_task_failed_signal():
    """Get or create the task_failed signal."""
    global task_failed
    if task_failed is None:
        from django.dispatch import Signal
        task_failed = Signal(
        )
    return task_failed

def get_task_scheduled_signal():
    """Get or create the task_scheduled signal."""
    global task_scheduled
    if task_scheduled is None:
        from django.dispatch import Signal
        task_scheduled = Signal(
        )
    return task_scheduled

def get_task_queue_updated_signal():
    """Get or create the task_queue_updated signal."""
    global task_queue_updated
    if task_queue_updated is None:
        from django.dispatch import Signal
        task_queue_updated = Signal(
        )
    return task_queue_updated


# ── User Profile Signals ─────────────────────────────────────

profile_updated = None
profile_completeness_changed = None
user_segment_changed = None

def get_profile_updated_signal():
    """Get or create the profile_updated signal."""
    global profile_updated
    if profile_updated is None:
        from django.dispatch import Signal
        profile_updated = Signal(
        )
    return profile_updated

def get_profile_completeness_changed_signal():
    """Get or create the profile_completeness_changed signal."""
    global profile_completeness_changed
    if profile_completeness_changed is None:
        from django.dispatch import Signal
        profile_completeness_changed = Signal(
        )
    return profile_completeness_changed

def get_user_segment_changed_signal():
    """Get or create the user_segment_changed signal."""
    global user_segment_changed
    if user_segment_changed is None:
        from django.dispatch import Signal
        user_segment_changed = Signal(
        )
    return user_segment_changed


# ── Analytics Signals ─────────────────────────────────────────────

analytics_updated = None
report_generated = None
dashboard_data_updated = None

def get_analytics_updated_signal():
    """Get or create the analytics_updated signal."""
    global analytics_updated
    if analytics_updated is None:
        from django.dispatch import Signal
        analytics_updated = Signal(
        )
    return analytics_updated

def get_report_generated_signal():
    """Get or create the report_generated signal."""
    global report_generated
    if report_generated is None:
        from django.dispatch import Signal
        report_generated = Signal(
        )
    return report_generated

def get_dashboard_data_updated_signal():
    """Get or create the dashboard_data_updated signal."""
    global dashboard_data_updated
    if dashboard_data_updated is None:
        from django.dispatch import Signal
        dashboard_data_updated = Signal(
        )
    return dashboard_data_updated


# ── Notification Signals ─────────────────────────────────────────

notification_created = None
notification_read = None
bulk_notification_sent = None

def get_notification_created_signal():
    """Get or create the notification_created signal."""
    global notification_created
    if notification_created is None:
        from django.dispatch import Signal
        notification_created = Signal(
        )
    return notification_created

def get_notification_read_signal():
    """Get or create the notification_read signal."""
    global notification_read
    if notification_read is None:
        from django.dispatch import Signal
        notification_read = Signal(
        )
    return notification_read

def get_bulk_notification_sent_signal():
    """Get or create the bulk_notification_sent signal."""
    global bulk_notification_sent
    if bulk_notification_sent is None:
        from django.dispatch import Signal
        bulk_notification_sent = Signal(
        )
    return bulk_notification_sent


# ── System Signals ─────────────────────────────────────────────

system_maintenance_started = None
system_maintenance_ended = None
cache_invalidated = None
webhook_triggered = None

def get_system_maintenance_started_signal():
    """Get or create the system_maintenance_started signal."""
    global system_maintenance_started
    if system_maintenance_started is None:
        from django.dispatch import Signal
        system_maintenance_started = Signal(
        )
    return system_maintenance_started

def get_system_maintenance_ended_signal():
    """Get or create the system_maintenance_ended signal."""
    global system_maintenance_ended
    if system_maintenance_ended is None:
        from django.dispatch import Signal
        system_maintenance_ended = Signal(
        )
    return system_maintenance_ended

def get_cache_invalidated_signal():
    """Get or create the cache_invalidated signal."""
    global cache_invalidated
    if cache_invalidated is None:
        from django.dispatch import Signal
        cache_invalidated = Signal(
        )
    return cache_invalidated

def get_webhook_triggered_signal():
    """Get or create the webhook_triggered signal."""
    global webhook_triggered
    if webhook_triggered is None:
        from django.dispatch import Signal
        webhook_triggered = Signal(
        )
    return webhook_triggered


# ── Popup signals ─────────────────────────────────────────────────

@receiver(post_save, sender='cms.Popup')
def popup_saved(sender, instance, **kwargs):
    """Invalidate popup cache."""
    try:
        from api.cms.services_new.CMSCacheService import CMSCacheService
        CMSCacheService.invalidate_popup(instance)
    except Exception:
        pass


# ── Menu signals ──────────────────────────────────────────────────

@receiver(post_save, sender='cms.Menu')
@receiver(post_delete, sender='cms.Menu')
def menu_saved(sender, instance, **kwargs):
    """Invalidate menu cache."""
    try:
        from api.cms.services_new.CMSCacheService import CMSCacheService
        CMSCacheService.invalidate_menu(instance)
    except Exception:
        pass


@receiver(post_save, sender='cms.MenuItem')
@receiver(post_delete, sender='cms.MenuItem')
def menu_item_saved(sender, instance, **kwargs):
    """Invalidate menu cache when item changes."""
    try:
        if instance.menu:
            instance.menu.invalidate_cache()
    except Exception:
        pass


# ── SiteSettings signals ──────────────────────────────────────────

@receiver(post_save, sender='cms.SiteSettings')
def site_settings_saved(sender, instance, **kwargs):
    """Invalidate settings cache."""
    try:
        from django.core.cache import cache
        cache.delete(f'site_setting_{instance.key}')
        cache.delete('site_settings_public')
        cache.delete('site_app_config')
        cache.delete('cms_public_settings')
    except Exception:
        pass


# ── SEOConfig signals ─────────────────────────────────────────────

@receiver(post_save, sender='cms.SEOConfig')
def seo_config_saved(sender, instance, **kwargs):
    """Invalidate SEO config cache."""
    try:
        from django.core.cache import cache
        cache.delete('seo_config_active')
    except Exception:
        pass


# ── Redirect signals ──────────────────────────────────────────────

@receiver(post_save, sender='cms.Redirect301')
@receiver(post_delete, sender='cms.Redirect301')
def redirect_saved(sender, instance, **kwargs):
    """Invalidate redirect cache."""
    try:
        from django.core.cache import cache
        cache.delete(f'redirect_{instance.from_url}')
        cache.delete('redirect_map')
    except Exception:
        pass


# ── Notification signals ──────────────────────────────────────────

@receiver(post_save, sender='cms.Notification')
def notification_saved(sender, instance, created, **kwargs):
    """Invalidate unread notification count cache."""
    try:
        from django.core.cache import cache
        if instance.user_id:
            cache.delete(f'notif_unread_{instance.user_id}')
    except Exception:
        pass


# ── CPALeadConfig signals ─────────────────────────────────────────

@receiver(post_save, sender='cms.CPALeadConfig')
def cpalead_config_saved(sender, instance, **kwargs):
    """Invalidate CPAlead config cache."""
    try:
        from django.core.cache import cache
        cache.delete('cpalead_config_active')
    except Exception:
        pass


# ── Testimonial signals ───────────────────────────────────────────

@receiver(post_save, sender='cms.Testimonial')
@receiver(post_delete, sender='cms.Testimonial')
def testimonial_saved(sender, instance, **kwargs):
    """Invalidate testimonial cache."""
    try:
        from django.core.cache import cache
        for limit in [3, 6, 10]:
            cache.delete(f'testimonials_featured_{limit}')
    except Exception:
        pass


# ── SocialLink signals ────────────────────────────────────────────

@receiver(post_save, sender='cms.SocialLink')
@receiver(post_delete, sender='cms.SocialLink')
def social_link_saved(sender, instance, **kwargs):
    """Invalidate social links cache."""
    try:
        from django.core.cache import cache
        cache.delete(f'social_links_{instance.location}')
        cache.delete('social_links_both')
        cache.delete('social_links_header')
        cache.delete('social_links_footer')
    except Exception:
        pass


# ── CPAlead Conversion → Loyalty ─────────────────────────────────

@receiver(post_save, sender='cms.ConversionLog')
def conversion_log_saved(sender, instance, created, **kwargs):
    """When a CPAlead conversion is confirmed, emit loyalty event."""
    if not created:
        return
    try:
        from api.cms.loyalty_bridge import CMSLoyaltyBridge
        CMSLoyaltyBridge.offer_completed(
            user=instance.user,
            offer_id=str(instance.offer_id),
            offer_title=instance.offer_title or '',
            coins_earned=float(instance.coins_awarded or 0),
            usd_earned=float(instance.payout_usd or 0),
        )
    except Exception as e:
        logger.debug(f"Loyalty offer_completed signal error: {e}")


# ── Quiz Attempt → Loyalty ───────────────────────────────────────

@receiver(post_save, sender='cms.QuizAttempt')
def quiz_attempt_saved(sender, instance, created, **kwargs):
    """When quiz is completed (score saved), emit loyalty event."""
    if not created or not getattr(instance, 'is_completed', False):
        return
    try:
        # Credit wallet
        try:
            from api.cms.wallet_bridge import CMSWalletBridge
            from decimal import Decimal
            if hasattr(instance, 'coins_earned') and instance.coins_earned:
                CMSWalletBridge.credit(
                    user=instance.user,
                    amount_usd=Decimal(str(getattr(instance, 'usd_earned', 0) or 0)),
                    source='quiz_reward',
                    ref_id=str(instance.id),
                    description=f'Quiz completed: {getattr(instance.quiz, "title", "")}',
                )
        except Exception as e:
            logger.debug(f"Quiz wallet credit failed: {e}")
        from api.cms.loyalty_bridge import CMSLoyaltyBridge
        CMSLoyaltyBridge.quiz_completed(
            user=instance.user,
            quiz_id=instance.quiz_template_id,
            quiz_title=getattr(instance.quiz_template, 'title', ''),
            score=float(getattr(instance, 'score_percent', 0)),
            coins_earned=float(getattr(instance, 'coins_awarded', 0)),
        )
        # Push notification
        from api.cms.notifications_push import CMSPushNotificationService
        CMSPushNotificationService.notify_reward_earned(
            user=instance.user,
            coins=float(getattr(instance, 'coins_awarded', 0)),
            source='Quiz',
        )
    except Exception as e:
        logger.debug(f"Loyalty quiz_completed signal error: {e}")


# ── Referral Conversion → Loyalty ───────────────────────────────

@receiver(post_save, sender='cms.ReferralEarning')
def referral_earning_saved(sender, instance, created, **kwargs):
    """When referral bonus is credited, emit loyalty event."""
    if not created:
        return
    try:
        from api.cms.loyalty_bridge import CMSLoyaltyBridge
        CMSLoyaltyBridge.referral_converted(
            referrer=instance.referrer,
            new_user=instance.referred_user,
            bonus_coins=float(instance.coins_awarded or 0),
        )
        # Push notification to referrer
        from api.cms.notifications_push import CMSPushNotificationService
        CMSPushNotificationService.notify_referral_bonus(
            user=instance.referrer,
            referred_username=getattr(instance.referred_user, 'username', ''),
            bonus_coins=float(instance.coins_awarded or 0),
        )
    except Exception as e:
        logger.debug(f"Loyalty referral_converted signal error: {e}")


# ── Streak Milestone → Loyalty + Push ───────────────────────────

@receiver(post_save, sender='cms.StreakRecord')
def streak_record_saved(sender, instance, created, **kwargs):
    """When streak milestone is hit, emit loyalty event + push."""
    if not getattr(instance, 'is_milestone', False):
        return
    try:
        from api.cms.loyalty_bridge import CMSLoyaltyBridge
        CMSLoyaltyBridge.streak_milestone(
            user=instance.user,
            streak_days=instance.current_streak,
            milestone_title=getattr(instance, 'milestone_title', f'{instance.current_streak}-Day Streak'),
            bonus_coins=float(getattr(instance, 'milestone_bonus', 0)),
        )
        from api.cms.notifications_push import CMSPushNotificationService
        CMSPushNotificationService.notify_streak_milestone(
            user=instance.user,
            days=instance.current_streak,
            title=getattr(instance, 'milestone_title', ''),
            bonus_coins=float(getattr(instance, 'milestone_bonus', 0)),
        )
    except Exception as e:
        logger.debug(f"Loyalty streak_milestone signal error: {e}")


# ── Level Up → Loyalty + Push ────────────────────────────────────

@receiver(post_save, sender='cms.UserProfile')
def user_profile_level_changed(sender, instance, created, **kwargs):
    """When user level changes, emit loyalty event + push."""
    if created:
        return
    try:
        # Check if level changed
        old = getattr(instance, '_pre_save_level', None)
        if old and old != instance.level:
            from api.cms.loyalty_bridge import CMSLoyaltyBridge
            CMSLoyaltyBridge.level_up(
                user=instance.user,
                new_level=instance.level,
                old_level=old,
            )
            from api.cms.notifications_push import CMSPushNotificationService
            CMSPushNotificationService.notify_level_up(
                user=instance.user,
                new_level=instance.level,
                level_name=getattr(instance, 'level_name', f'Level {instance.level}'),
            )
    except Exception as e:
        logger.debug(f"Level up signal error: {e}")


@receiver(pre_save, sender='cms.UserProfile')
def user_profile_pre_save(sender, instance, **kwargs):
    """Cache level before save to detect changes."""
    try:
        old = sender.objects.get(pk=instance.pk)
        instance._pre_save_level = old.level
    except sender.DoesNotExist:
        instance._pre_save_level = None


# ══════════════════════════════════════════════════════════════════════════════
# NEW MODEL SIGNALS — adapter-wired cross-system events
# ══════════════════════════════════════════════════════════════════════════════

@receiver(post_save, sender='cms.BannerReward')
def banner_reward_created(sender, instance, created, **kwargs):
    """When a BannerReward is saved and processed, credit wallet + notify."""
    if not created or not instance.is_processed:
        return
    try:
        from api.cms.adapters import WalletAdapter, NotificationAdapter, AuditAdapter
        from decimal import Decimal
        WalletAdapter.credit(
            user=instance.user,
            amount_usd=Decimal(str(instance.amount)),
            source='banner_reward',
            ref_id=str(instance.uuid),
            description=f'Banner reward: {instance.reward_type}',
        )
        NotificationAdapter.notify_reward_earned(instance.user, float(instance.amount))
        AuditAdapter.reward_issued(instance.user, float(instance.amount), 'banner_reward')
    except Exception as e:
        logger.warning(f"[Signal] banner_reward_created error: {e}")


@receiver(post_save, sender='cms.SurveyCompletion')
def survey_completion_reward(sender, instance, created, **kwargs):
    """When a survey is completed, fire all reward adapters."""
    if instance.status != 'completed':
        return
    try:
        from api.cms.adapters import (
            GamificationAdapter, LoyaltyAdapter, ReferralAdapter,
            PostbackAdapter, NotificationAdapter, AnalyticsAdapter, AuditAdapter,
        )
        user = instance.user
        survey_id = str(instance.survey_id)
        GamificationAdapter.on_survey_completed(user, survey_id)
        LoyaltyAdapter.on_survey_completed(user)
        ReferralAdapter.on_survey_completed(user, survey_id)
        PostbackAdapter.on_survey_completed(user, survey_id)
        AnalyticsAdapter.survey_completed(user, survey_id)
        NotificationAdapter.send(
            user, 'Survey completed!',
            'Thank you for completing the survey. Your reward is on its way.',
            notif_type='survey_completed',
        )
        AuditAdapter.log('cms.survey.completed', user, 'survey', survey_id)
    except Exception as e:
        logger.warning(f"[Signal] survey_completion_reward error: {e}")


@receiver(post_save, sender='cms.WorkflowState')
def workflow_state_changed(sender, instance, created, **kwargs):
    """Notify assigned reviewer + fire audit log on workflow state change."""
    try:
        from api.cms.adapters import NotificationAdapter, AuditAdapter
        if instance.assigned_to:
            action_label = 'submitted' if instance.state == 'review' else instance.state
            NotificationAdapter.notify_workflow_action(
                instance.assigned_to, action_label, f'{instance.content_type}:{instance.object_id}'
            )
        AuditAdapter.log(
            f'cms.workflow.{instance.state}',
            instance.created_by,
            instance.content_type,
            str(instance.object_id),
        )
    except Exception as e:
        logger.debug(f"[Signal] workflow_state_changed error: {e}")


@receiver(post_save, sender='cms.EarningStreak')
def earning_streak_milestone_check(sender, instance, **kwargs):
    """Check for streak milestones after each streak update."""
    try:
        from api.cms.models_new.leaderboard import StreakMilestone
        from api.cms.adapters import GamificationAdapter, NotificationAdapter
        milestones = StreakMilestone.objects.filter(
            streak_days=instance.current_streak, is_active=True
        )
        for milestone in milestones:
            GamificationAdapter.on_streak_milestone(instance.user, instance.current_streak)
            NotificationAdapter.send(
                instance.user,
                f'🔥 {instance.current_streak}-Day Streak!',
                milestone.description or f"You've hit a {instance.current_streak}-day earning streak!",
                notif_type='streak_milestone',
                data={'streak_days': instance.current_streak, 'bonus_coins': milestone.bonus_coins},
            )
    except Exception as e:
        logger.debug(f"[Signal] earning_streak_milestone_check error: {e}")


@receiver(post_save, sender='cms.LeaderboardEntry')
def leaderboard_rank_change(sender, instance, **kwargs):
    """Notify user when they reach top ranks on the leaderboard."""
    try:
        from api.cms.adapters import NotificationAdapter
        if instance.rank and instance.rank <= 3:
            medals = {1: '🥇', 2: '🥈', 3: '🥉'}
            medal = medals.get(instance.rank, '🏆')
            NotificationAdapter.send(
                instance.user,
                f'{medal} You are #{instance.rank} on the Leaderboard!',
                f'Keep earning to stay at the top.',
                notif_type='leaderboard_rank',
                data={'rank': instance.rank, 'score': float(instance.score)},
            )
    except Exception as e:
        logger.debug(f"[Signal] leaderboard_rank_change error: {e}")


@receiver(post_save, sender='cms.VirtualTransaction')
def virtual_transaction_sync(sender, instance, created, **kwargs):
    """Sync virtual transaction to analytics on creation."""
    if not created:
        return
    try:
        from api.cms.adapters import AnalyticsAdapter, AuditAdapter
        AnalyticsAdapter.track('virtual_transaction', instance.user, {
            'tx_type': instance.tx_type,
            'amount': float(instance.amount),
            'usd_equivalent': float(instance.usd_equivalent or 0),
        })
        AuditAdapter.log(
            f'cms.virtual_tx.{instance.tx_type}',
            instance.user, 'virtual_transaction', str(instance.uuid),
            {'amount': float(instance.amount)},
        )
    except Exception as e:
        logger.debug(f"[Signal] virtual_transaction_sync error: {e}")


@receiver(post_save, sender='cms.FormSubmission')
def form_submission_reward(sender, instance, created, **kwargs):
    """Award XP and fire analytics when a form is submitted."""
    if not created:
        return
    try:
        from api.cms.adapters import GamificationAdapter, AnalyticsAdapter
        GamificationAdapter.award_xp(instance.user, 5, source='form_submission', ref_id=str(instance.uuid))
        AnalyticsAdapter.form_submission(instance.user, str(instance.form_id))
    except Exception as e:
        logger.debug(f"[Signal] form_submission_reward error: {e}")
