# engagement/receivers.py
"""
Signal receivers for engagement system.
Handles model signals, user signals, and system events.
"""
import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from .services.analytics_service import AnalyticsService
from .services.notification_service import NotificationService
from .services.gamification_engine import GamificationEngine

logger = logging.getLogger(__name__)


# ── User Signal Receivers ─────────────────────────────────────────────────────

@receiver(post_save, sender=get_user_model())
def user_created(sender, instance, created, **kwargs):
    """
    Handle user creation.
    """
    if created:
        try:
            # Create initial user profile data
            _create_user_profile(instance)
            
            # Send welcome notification
            NotificationService.send(
                instance,
                "welcome",
                title="Welcome to Engagement!",
                body="Get started with your first check-in and spin!",
                data={"tutorial_step": 1}
            )
            
            # Record analytics
            AnalyticsService.record(
                instance,
                "user_registered",
                properties={
                    "registration_date": instance.date_joined.isoformat(),
                    "user_type": "standard"
                }
            )
            
            # Trigger gamification engine
            GamificationEngine.on_user_registered(instance)
            
            logger.info(f"New user profile created for {instance.username}")
            
        except Exception as exc:
            logger.error(f"Failed to create user profile for {instance.username}: {exc}")


@receiver(pre_save, sender=get_user_model())
def user_updated(sender, instance, **kwargs):
    """
    Handle user updates.
    """
    try:
        # Get old user data if available
        if instance.pk:
            old_user = sender.objects.get(pk=instance.pk)
            
            # Check for status changes
            if hasattr(old_user, 'status') and hasattr(instance, 'status'):
                if old_user.status != instance.status:
                    _handle_user_status_change(instance, old_user.status, instance.status)
            
            # Check for subscription changes
            if hasattr(old_user, 'has_premium') and hasattr(instance, 'has_premium'):
                if old_user.has_premium != instance.has_premium:
                    _handle_subscription_change(instance, instance.has_premium)
            
    except Exception as exc:
        logger.error(f"Failed to handle user update: {exc}")


def _create_user_profile(user):
    """Create initial user profile data."""
    from .models.xp import UserXP
    from .models.quest import UserQuest
    
    # Create XP record
    UserXP.objects.get_or_create(
        user=user,
        defaults={
            'tenant': getattr(user, 'tenant', None),
            'total_xp': 0,
            'level': 1,
        }
    )
    
    # Create initial daily quests
    from .services.quest_service import QuestService
    QuestService.init_daily_quests(user)


def _handle_user_status_change(user, old_status, new_status):
    """Handle user status changes."""
    if new_status in ['suspended', 'banned']:
        # Revoke active sessions
        _revoke_user_sessions(user)
        
        # Send notification
        NotificationService.send(
            user,
            "account_status",
            title=f"Account Status: {new_status.title()}",
            body=f"Your account status has been changed to {new_status}.",
            data={"old_status": old_status, "new_status": new_status}
        )
        
        # Record analytics
        AnalyticsService.record(
            user,
            "account_status_changed",
            properties={
                "old_status": old_status,
                "new_status": new_status
            }
        )


def _handle_subscription_change(user, has_premium):
    """Handle subscription changes."""
    if has_premium:
        NotificationService.send(
            user,
            "subscription",
            title="Premium Activated!",
            body="Enjoy your premium benefits and exclusive features.",
            data={"premium_activated": True}
        )
        
        AnalyticsService.record(
            user,
            "premium_activated",
            properties={"subscription_type": "premium"}
        )
    else:
        NotificationService.send(
            user,
            "subscription",
            title="Premium Deactivated",
            body="Your premium benefits have been deactivated.",
            data={"premium_deactivated": True}
        )
        
        AnalyticsService.record(
            user,
            "premium_deactivated",
            properties={"subscription_type": "free"}
        )


def _revoke_user_sessions(user):
    """Revoke all user sessions."""
    try:
        from django.contrib.sessions.models import Session
        
        # Remove all user sessions
        Session.objects.filter(
            session_data__contains=f'"user_id":{user.id}'
        ).delete()
        
        logger.info(f"Revoked all sessions for user {user.username}")
        
    except Exception as exc:
        logger.error(f"Failed to revoke sessions for {user.username}: {exc}")


# ── Model Signal Receivers ─────────────────────────────────────────────────────

@receiver(post_save, sender='engagement.DailyCheckIn')
def daily_checkin_saved(sender, instance, created, **kwargs):
    """
    Handle daily check-in save.
    """
    if created:
        try:
            # Invalidate user stats cache
            cache.delete(f"user_stats_{instance.user.id}")
            
            # Update streak analytics
            AnalyticsService.record(
                instance.user,
                "checkin_completed",
                properties={
                    "streak": instance.consecutive_days,
                    "coins_earned": float(instance.coins_earned),
                    "xp_earned": instance.xp_earned,
                    "bonus_claimed": instance.bonus_claimed,
                    "shield_used": instance.streak_shield_used
                }
            )
            
            logger.info(f"Check-in completed for user {instance.user.username}")
            
        except Exception as exc:
            logger.error(f"Failed to handle check-in save: {exc}")


@receiver(post_save, sender='engagement.SpinWheel')
def spin_wheel_saved(sender, instance, created, **kwargs):
    """
    Handle spin wheel save.
    """
    if created:
        try:
            # Invalidate user stats cache
            cache.delete(f"user_stats_{instance.user.id}")
            
            # Update spin analytics
            AnalyticsService.record(
                instance.user,
                "spin_completed",
                properties={
                    "coins_won": float(instance.coins_won),
                    "xp_earned": instance.xp_earned,
                    "is_boosted": instance.is_boosted,
                    "outcome_idx": instance.outcome_idx
                }
            )
            
            logger.info(f"Spin completed for user {instance.user.username}")
            
        except Exception as exc:
            logger.error(f"Failed to handle spin save: {exc}")


@receiver(post_save, sender='engagement.UserAchievement')
def user_achievement_saved(sender, instance, created, **kwargs):
    """
    Handle user achievement save.
    """
    if instance.unlocked_at and created:
        try:
            # Update achievement analytics
            AnalyticsService.record(
                instance.user,
                "achievement_unlocked",
                properties={
                    "achievement_id": instance.achievement.id,
                    "achievement_name": instance.achievement.name,
                    "achievement_type": instance.achievement.type,
                    "difficulty": instance.achievement.difficulty
                }
            )
            
            logger.info(f"Achievement unlocked for user {instance.user.username}: {instance.achievement.name}")
            
        except Exception as exc:
            logger.error(f"Failed to handle achievement save: {exc}")


@receiver(post_save, sender='engagement.UserQuest')
def user_quest_saved(sender, instance, created, **kwargs):
    """
    Handle user quest save.
    """
    try:
        # Update quest analytics on status change
        if instance.status == 'completed':
            AnalyticsService.record(
                instance.user,
                "quest_completed",
                properties={
                    "quest_id": instance.quest.id,
                    "quest_name": instance.quest.name,
                    "quest_type": instance.quest.type,
                    "difficulty": instance.quest.difficulty
                }
            )
            
            logger.info(f"Quest completed for user {instance.user.username}: {instance.quest.name}")
        
    except Exception as exc:
        logger.error(f"Failed to handle quest save: {exc}")


@receiver(post_save, sender='engagement.ShopPurchase')
def shop_purchase_saved(sender, instance, created, **kwargs):
    """
    Handle shop purchase save.
    """
    if instance.status == 'completed':
        try:
            # Update purchase analytics
            AnalyticsService.record(
                instance.user,
                "shop_purchase",
                properties={
                    "item_id": instance.item.id,
                    "item_name": instance.item.name,
                    "item_type": instance.item.type,
                    "coins_spent": float(instance.coins_spent),
                    "quantity": instance.quantity
                }
            )
            
            logger.info(f"Shop purchase completed for user {instance.user.username}: {instance.item.name}")
            
        except Exception as exc:
            logger.error(f"Failed to handle shop purchase save: {exc}")


# ── System Signal Receivers ─────────────────────────────────────────────────────

@receiver(post_save, sender='engagement.Leaderboard')
def leaderboard_saved(sender, instance, created, **kwargs):
    """
    Handle leaderboard save.
    """
    if created:
        try:
            # Update leaderboard analytics
            AnalyticsService.record(
                instance.user,
                "leaderboard_entry",
                properties={
                    "rank": instance.rank,
                    "total_coins": float(instance.total_coins_earned),
                    "total_xp": instance.total_xp_earned,
                    "date": instance.date.isoformat()
                }
            )
            
            # Check for top ranks
            if instance.rank <= 10:
                NotificationService.send(
                    instance.user,
                    "leaderboard",
                    title=f"Top {instance.rank}!",
                    body=f"You're ranked #{instance.rank} on today's leaderboard!",
                    data={"rank": instance.rank, "date": instance.date.isoformat()}
                )
            
            logger.info(f"Leaderboard entry created for user {instance.user.username}: rank {instance.rank}")
            
        except Exception as exc:
            logger.error(f"Failed to handle leaderboard save: {exc}")


@receiver(post_delete, sender='engagement.DailyCheckIn')
def daily_checkin_deleted(sender, instance, **kwargs):
    """
    Handle daily check-in deletion.
    """
    try:
        # Invalidate user stats cache
        cache.delete(f"user_stats_{instance.user.id}")
        
        # Record deletion analytics
        AnalyticsService.record(
            instance.user,
            "checkin_deleted",
            properties={
                "date": instance.date.isoformat(),
                "coins_earned": float(instance.coins_earned),
                "xp_earned": instance.xp_earned
            }
        )
        
        logger.info(f"Check-in deleted for user {instance.user.username}")
        
    except Exception as exc:
        logger.error(f"Failed to handle check-in deletion: {exc}")


@receiver(post_delete, sender='engagement.SpinWheel')
def spin_wheel_deleted(sender, instance, **kwargs):
    """
    Handle spin wheel deletion.
    """
    try:
        # Invalidate user stats cache
        cache.delete(f"user_stats_{instance.user.id}")
        
        # Record deletion analytics
        AnalyticsService.record(
            instance.user,
            "spin_deleted",
            properties={
                "spun_at": instance.spun_at.isoformat(),
                "coins_won": float(instance.coins_won),
                "xp_earned": instance.xp_earned
            }
        )
        
        logger.info(f"Spin deleted for user {instance.user.username}")
        
    except Exception as exc:
        logger.error(f"Failed to handle spin deletion: {exc}")


# ── Cache Invalidation Receivers ─────────────────────────────────────────────────

@receiver(post_save, sender='engagement.UserXP')
def user_xp_saved(sender, instance, **kwargs):
    """
    Handle user XP save and invalidate cache.
    """
    try:
        # Invalidate user stats cache
        cache.delete(f"user_stats_{instance.user.id}")
        cache.delete(f"user_xp_{instance.user.id}")
        
        # Check for level up
        old_level = kwargs.get('old_level', 1)
        if instance.level > old_level:
            NotificationService.send(
                instance.user,
                "level_up",
                title=f"Level {instance.level}!",
                body=f"Congratulations! You've reached level {instance.level}.",
                data={"old_level": old_level, "new_level": instance.level}
            )
        
        logger.info(f"XP updated for user {instance.user.username}: level {instance.level}")
        
    except Exception as exc:
        logger.error(f"Failed to handle XP save: {exc}")


@receiver(post_save, sender='engagement.UserQuest')
def user_quest_saved_cache(sender, instance, **kwargs):
    """
    Handle user quest save and invalidate cache.
    """
    try:
        # Invalidate user stats cache
        cache.delete(f"user_stats_{instance.user.id}")
        cache.delete(f"user_quests_{instance.user.id}")
        
        logger.info(f"Quest updated for user {instance.user.username}: {instance.quest.name}")
        
    except Exception as exc:
        logger.error(f"Failed to handle quest cache invalidation: {exc}")


# ── Scheduled Task Receivers ───────────────────────────────────────────────────

@receiver(post_save, sender='engagement.LeaderboardSeason')
def leaderboard_season_saved(sender, instance, created, **kwargs):
    """
    Handle leaderboard season save.
    """
    if created:
        try:
            # Notify about new season
            from .services.notification_service import NotificationService
            
            # Get all active users
            User = get_user_model()
            active_users = User.objects.filter(status='active')
            
            for user in active_users:
                NotificationService.send(
                    user,
                    "season_start",
                    title=f"New {instance.period.title()} Season!",
                    body=f"A new {instance.period} season has started. Compete for rewards!",
                    data={
                        "season_id": instance.id,
                        "period": instance.period,
                        "start_date": instance.start_date.isoformat(),
                        "end_date": instance.end_date.isoformat()
                    }
                )
            
            logger.info(f"New leaderboard season created: {instance.period} {instance.id}")
            
        except Exception as exc:
            logger.error(f"Failed to handle season save: {exc}")


# ── Error Handling Receivers ───────────────────────────────────────────────────

@receiver(post_save, sender='engagement.AntiCheatLog')
def anti_cheat_log_saved(sender, instance, created, **kwargs):
    """
    Handle anti-cheat log save.
    """
    if created:
        try:
            # Check for high-risk violations
            if instance.risk_level in ['high', 'critical']:
                NotificationService.send(
                    instance.user,
                    "security_alert",
                    title="Security Alert",
                    body="Suspicious activity detected on your account.",
                    data={
                        "risk_level": instance.risk_level,
                        "rule_type": instance.rule_type,
                        "timestamp": instance.created_at.isoformat()
                    }
                )
            
            # Log security event
            logger.warning(
                f"Anti-cheat violation: user={instance.user.username}, "
                f"risk={instance.risk_level}, rule={instance.rule_type}"
            )
            
        except Exception as exc:
            logger.error(f"Failed to handle anti-cheat log: {exc}")


# ── Maintenance Receivers ─────────────────────────────────────────────────────

@receiver(post_save, sender='engagement.WebhookDelivery')
def webhook_delivery_saved(sender, instance, created, **kwargs):
    """
    Handle webhook delivery save.
    """
    try:
        # Update webhook endpoint statistics
        endpoint = instance.endpoint
        if instance.status == 'delivered':
            endpoint.success_count += 1
        elif instance.status in ['failed', 'abandoned']:
            endpoint.failure_count += 1
        
        endpoint.save(update_fields=['success_count', 'failure_count'])
        
        # Log webhook delivery
        logger.info(
            f"Webhook delivery: {instance.event_type} → {endpoint.url} "
            f"({instance.status})"
        )
        
    except Exception as exc:
        logger.error(f"Failed to handle webhook delivery: {exc}")


# ── Utility Functions ─────────────────────────────────────────────────────────

def invalidate_user_cache(user_id):
    """
    Invalidate all cache entries for a user.
    """
    cache_keys = [
        f"user_stats_{user_id}",
        f"user_xp_{user_id}",
        f"user_quests_{user_id}",
        f"user_achievements_{user_id}",
        f"user_notifications_{user_id}",
    ]
    
    for key in cache_keys:
        cache.delete(key)


def get_user_context(user):
    """
    Get user context for analytics and notifications.
    """
    return {
        'user_id': user.id,
        'username': user.username,
        'email': user.email,
        'tenant_id': getattr(user, 'tenant_id', None),
        'status': getattr(user, 'status', 'active'),
        'has_premium': getattr(user, 'has_premium', False),
        'date_joined': user.date_joined.isoformat(),
    }


# ── Bulk Operation Receivers ───────────────────────────────────────────────────

def handle_bulk_operation(model_class, operation, instances):
    """
    Handle bulk operations with proper cache invalidation.
    """
    try:
        # Perform bulk operation
        if operation == 'create':
            model_class.objects.bulk_create(instances)
        elif operation == 'update':
            model_class.objects.bulk_update(instances, ['updated_at'])
        elif operation == 'delete':
            model_class.objects.bulk_delete(instances)
        
        # Invalidate cache for affected users
        user_ids = set()
        for instance in instances:
            if hasattr(instance, 'user'):
                user_ids.add(instance.user.id)
        
        for user_id in user_ids:
            invalidate_user_cache(user_id)
        
        logger.info(f"Bulk {operation} completed for {model_class.__name__}: {len(instances)} instances")
        
    except Exception as exc:
        logger.error(f"Failed bulk {operation} for {model_class.__name__}: {exc}")
        raise


# ── Signal Connection Management ───────────────────────────────────────────────

def connect_engagement_signals():
    """
    Connect all engagement signals.
    """
    try:
        # Import models to ensure signals are connected
        from .models.checkin import DailyCheckIn
        from .models.spinwheel import SpinWheel
        from .models.achievement import UserAchievement
        from .models.quest import UserQuest
        from .models.shop import ShopPurchase
        from .models.leaderboard import Leaderboard
        from .models.xp import UserXP
        from .models.webhook import WebhookDelivery
        from .models.anti_cheat import AntiCheatLog
        
        logger.info("Engagement signals connected successfully")
        
    except Exception as exc:
        logger.error(f"Failed to connect engagement signals: {exc}")


def disconnect_engagement_signals():
    """
    Disconnect all engagement signals.
    """
    try:
        # Disconnect signals here if needed
        logger.info("Engagement signals disconnected")
        
    except Exception as exc:
        logger.error(f"Failed to disconnect engagement signals: {exc}")


# Auto-connect signals on module import
try:
    connect_engagement_signals()
except Exception:
    # Silently ignore if signals can't be connected during import
    pass
