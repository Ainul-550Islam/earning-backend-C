"""
Django Signals for Offer Routing System

This module defines signals for handling model save/delete events,
including analytics updates, cache invalidation, and validation.
"""

from django.db.models.signals import post_save, pre_save, post_delete, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache
import logging

from .models import (
    RoutingDecisionLog, OfferRoutingCap, UserOfferCap,
    RoutingABTest, RoutingConfig, RoutePerformanceStat,
    UserOfferHistory, OfferScore, UserPreferenceVector
,
    ABTestAssignment, ABTestResult, FallbackRule, GeoRouteRule, CapOverride, DefaultOfferPool, OfferRoute)
from .services.analytics import analytics_service
from .services.cache import cache_service

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=RoutingDecisionLog)
def routing_decision_pre_save(sender, instance, **kwargs):
    """
    Handle pre-save signal for RoutingDecisionLog.
    Validates decision data before saving.
    """
    try:
        # Validate required fields
        if not instance.user_id:
            raise ValueError("User ID is required for routing decisions")
        
        if not instance.offer_id and not instance.route_id:
            raise ValueError("Either offer_id or route_id is required")
        
        # Validate score range
        if instance.score and (instance.score < 0 or instance.score > 100):
            logger.warning(f"Invalid score {instance.score} for routing decision {instance.id}")
            instance.score = max(0, min(100, instance.score))
        
        # Validate response time
        if instance.response_time_ms and instance.response_time_ms < 0:
            logger.warning(f"Invalid response time {instance.response_time_ms} for routing decision {instance.id}")
            instance.response_time_ms = max(0, instance.response_time_ms)
        
        logger.debug(f"Pre-save validation for routing decision {instance.id}")
        
    except Exception as e:
        logger.error(f"Error in routing_decision_pre_save: {e}")
        raise


@receiver(post_save, sender=RoutingDecisionLog)
def routing_decision_post_save(sender, instance, created, **kwargs):
    """
    Handle post-save signal for RoutingDecisionLog.
    Triggers analytics updates and cache operations.
    """
    try:
        if created:
            logger.info(f"New routing decision logged: {instance.id} for user {instance.user_id}")
            
            # Update analytics in background
            from .tasks.analytics import update_user_analytics
            update_user_analytics.delay(
                user_id=instance.user_id,
                decision_id=instance.id
            )
            
            # Invalidate user routing cache
            if instance.user_id:
                cache_keys = [
                    f"routing:user_{instance.user_id}:*",
                    f"offer_scores:user_{instance.user_id}:*",
                    f"user_caps:user_{instance.user_id}:*"
                ]
                cache_service.delete_multiple(cache_keys)
            
            # Update real-time metrics
            from .tasks.monitoring import update_real_time_metrics
            update_real_time_metrics.delay(
                tenant_id=instance.user.tenant_id if hasattr(instance.user, 'tenant') else None,
                decision_data={
                    'user_id': instance.user_id,
                    'offer_id': instance.offer_id,
                    'score': instance.score,
                    'response_time_ms': instance.response_time_ms,
                    'cache_hit': instance.cache_hit
                }
            )
        
        logger.debug(f"Post-save processing for routing decision {instance.id}")
        
    except Exception as e:
        logger.error(f"Error in routing_decision_post_save: {e}")


@receiver(pre_save, sender=OfferRoutingCap)
def routing_cap_pre_save(sender, instance, **kwargs):
    """
    Handle pre-save signal for OfferRoutingCap.
    Validates cap configuration before saving.
    """
    try:
        # Validate cap value
        if instance.cap_value and instance.cap_value <= 0:
            logger.warning(f"Invalid cap value {instance.cap_value} for routing cap {instance.id}")
            instance.cap_value = max(1, instance.cap_value)
        
        # Validate cap type
        valid_types = ['daily', 'hourly', 'total', 'monthly']
        if instance.cap_type not in valid_types:
            logger.warning(f"Invalid cap type {instance.cap_type} for routing cap {instance.id}")
            instance.cap_type = 'daily'  # Default to daily
        
        logger.debug(f"Pre-save validation for routing cap {instance.id}")
        
    except Exception as e:
        logger.error(f"Error in routing_cap_pre_save: {e}")
        raise


@receiver(post_save, sender=OfferRoutingCap)
def routing_cap_post_save(sender, instance, **kwargs):
    """
    Handle post-save signal for OfferRoutingCap.
    Triggers cache invalidation and analytics updates.
    """
    try:
        logger.info(f"Routing cap updated: {instance.id} for offer {instance.offer_id}")
        
        # Invalidate routing cache for this offer
        if instance.offer_id:
            cache_keys = [
                f"routing:offer_{instance.offer_id}:*",
                f"offer_scores:offer_{instance.offer_id}:*",
                f"global_caps:offer_{instance.offer_id}"
            ]
            cache_service.delete_multiple(cache_keys)
        
        # Update cap analytics
        from .tasks.analytics import update_cap_analytics
        update_cap_analytics.delay(
            cap_id=instance.id,
            action='update'
        )
        
        # Check if cap is near limit
        if instance.current_count and instance.cap_value:
            usage_percentage = (instance.current_count / instance.cap_value) * 100
            
            if usage_percentage >= 90:
                from .tasks.monitoring import send_cap_alert
                send_cap_alert.delay(
                    cap_id=instance.id,
                    usage_percentage=usage_percentage,
                    alert_type='high_usage'
                )
        
        logger.debug(f"Post-save processing for routing cap {instance.id}")
        
    except Exception as e:
        logger.error(f"Error in routing_cap_post_save: {e}")


@receiver(post_save, sender=RoutingConfig)
def routing_config_post_save(sender, instance, **kwargs):
    """
    Handle post-save signal for RoutingConfig.
    Triggers configuration updates and cache clearing.
    """
    try:
        logger.info(f"Routing config updated: {instance.id} for tenant {instance.tenant_id}")
        
        # Clear all routing cache for this tenant
        if instance.tenant_id:
            cache_keys = [
                f"routing:tenant_{instance.tenant_id}:*",
                f"config:tenant_{instance.tenant_id}:*",
                f"personalization:tenant_{instance.tenant_id}:*"
            ]
            cache_service.delete_multiple(cache_keys)
        
        # Update routing engine configuration
        from .tasks.core import update_routing_config
        update_routing_config.delay(
            tenant_id=instance.tenant_id,
            config_id=instance.id
        )
        
        logger.debug(f"Post-save processing for routing config {instance.id}")
        
    except Exception as e:
        logger.error(f"Error in routing_config_post_save: {e}")


@receiver(pre_save, sender=UserOfferCap)
def user_cap_pre_save(sender, instance, **kwargs):
    """
    Handle pre-save signal for UserOfferCap.
    Validates user-specific caps before saving.
    """
    try:
        # Validate daily cap reset logic
        if instance.cap_type == 'daily':
            today = timezone.now().date()
            
            if instance.reset_at and instance.reset_at.date() == today:
                if instance.shown_today > 0:
                    logger.info(f"Resetting daily cap for user {instance.user_id}, offer {instance.offer_id}")
                    instance.shown_today = 0
                    instance.reset_at = timezone.now()
        
        # Validate cap limits
        if instance.max_shows_per_day and instance.max_shows_per_day > 1000:
            logger.warning(f"High daily cap {instance.max_shows_per_day} for user {instance.user_id}")
            instance.max_shows_per_day = 1000
        
        logger.debug(f"Pre-save validation for user cap {instance.id}")
        
    except Exception as e:
        logger.error(f"Error in user_cap_pre_save: {e}")
        raise


@receiver(post_save, sender=UserOfferCap)
def user_cap_post_save(sender, instance, **kwargs):
    """
    Handle post-save signal for UserOfferCap.
    Triggers user cache updates and analytics.
    """
    try:
        logger.debug(f"User cap updated: {instance.id} for user {instance.user_id}")
        
        # Update user-specific cache
        if instance.user_id and instance.offer_id:
            cache_keys = [
                f"user_caps:user_{instance.user_id}:offer_{instance.offer_id}",
                f"routing:user_{instance.user_id}:*"
            ]
            cache_service.delete_multiple(cache_keys)
        
        # Update user analytics
        from .tasks.analytics import update_user_cap_analytics
        update_user_cap_analytics.delay(
            user_id=instance.user_id,
            cap_id=instance.id
        )
        
        logger.debug(f"Post-save processing for user cap {instance.id}")
        
    except Exception as e:
        logger.error(f"Error in user_cap_post_save: {e}")


@receiver(post_save, sender=RoutingABTest)
def ab_test_post_save(sender, instance, **kwargs):
    """
    Handle post-save signal for RoutingABTest.
    Triggers test setup and cache updates.
    """
    try:
        logger.info(f"A/B test updated: {instance.id} for tenant {instance.tenant_id}")
        
        # Clear routing cache for test routes
        if instance.control_route_id and instance.variant_route_id:
            route_ids = [instance.control_route_id, instance.variant_route_id]
            for route_id in route_ids:
                cache_keys = [
                    f"routing:route_{route_id}:*",
                    f"targeting:route_{route_id}:*",
                    f"scoring:route_{route_id}:*"
                ]
                cache_service.delete_multiple(cache_keys)
        
        # Update test analytics
        from .tasks.ab_test import update_test_analytics
        update_test_analytics.delay(
            test_id=instance.id,
            action='update'
        )
        
        # If test is starting, initialize assignments
        if instance.is_active and instance.started_at:
            from .tasks.ab_test import initialize_test_assignments
            initialize_test_assignments.delay(
                test_id=instance.id
            )
        
        logger.debug(f"Post-save processing for A/B test {instance.id}")
        
    except Exception as e:
        logger.error(f"Error in ab_test_post_save: {e}")


@receiver(post_save, sender=RoutePerformanceStat)
def performance_stat_post_save(sender, instance, **kwargs):
    """
    Handle post-save signal for RoutePerformanceStat.
    Triggers performance analytics updates.
    """
    try:
        logger.debug(f"Performance stat saved: {instance.id} for tenant {instance.tenant_id}")
        
        # Update performance analytics
        from .tasks.analytics import update_performance_analytics
        update_performance_analytics.delay(
            stat_id=instance.id,
            tenant_id=instance.tenant_id
        )
        
        # Check for performance alerts
        if instance.impressions > 0:
            conversion_rate = (instance.conversions / instance.impressions) * 100
            
            if conversion_rate < 1.0:  # Low conversion rate alert
                from .tasks.monitoring import send_performance_alert
                send_performance_alert.delay(
                    tenant_id=instance.tenant_id,
                    stat_id=instance.id,
                    alert_type='low_conversion',
                    conversion_rate=conversion_rate
                )
        
        logger.debug(f"Post-save processing for performance stat {instance.id}")
        
    except Exception as e:
        logger.error(f"Error in performance_stat_post_save: {e}")


@receiver(post_save, sender=UserOfferHistory)
def offer_history_post_save(sender, instance, **kwargs):
    """
    Handle post-save signal for UserOfferHistory.
    Triggers history analytics and preference updates.
    """
    try:
        logger.debug(f"Offer history saved: {instance.id} for user {instance.user_id}")
        
        # Update user analytics
        from .tasks.analytics import update_user_history_analytics
        update_user_history_analytics.delay(
            user_id=instance.user_id,
            history_id=instance.id
        )
        
        # Update user preferences if conversion
        if instance.completed_at and instance.offer_id:
            from .tasks.personalization import update_user_preferences
            update_user_preferences.delay(
                user_id=instance.user_id,
                offer_id=instance.offer_id,
                interaction_type='conversion'
            )
        
        # Clear user routing cache
        if instance.user_id:
            cache_keys = [
                f"routing:user_{instance.user_id}:*",
                f"offer_scores:user_{instance.user_id}:*",
                f"user_preferences:user_{instance.user_id}"
            ]
            cache_service.delete_multiple(cache_keys)
        
        logger.debug(f"Post-save processing for offer history {instance.id}")
        
    except Exception as e:
        logger.error(f"Error in offer_history_post_save: {e}")


@receiver(post_save, sender=OfferScore)
def offer_score_post_save(sender, instance, **kwargs):
    """
    Handle post-save signal for OfferScore.
    Triggers score analytics and cache updates.
    """
    try:
        logger.debug(f"Offer score saved: {instance.id} for user {instance.user_id}")
        
        # Update score cache
        if instance.user_id and instance.offer_id:
            cache_key = f"offer_scores:user_{instance.user_id}:offer_{instance.offer_id}"
            cache_service.set_offer_score(
                user_id=instance.user_id,
                offer_id=instance.offer_id,
                score_data={
                    'score': instance.score,
                    'epc': instance.epc,
                    'cr': instance.cr,
                    'relevance': instance.relevance,
                    'freshness': instance.freshness,
                    'calculated_at': instance.calculated_at.isoformat()
                }
            )
        
        # Update score analytics
        from .tasks.analytics import update_score_analytics
        update_score_analytics.delay(
            score_id=instance.id,
            tenant_id=instance.user.tenant_id if hasattr(instance.user, 'tenant') else None
        )
        
        logger.debug(f"Post-save processing for offer score {instance.id}")
        
    except Exception as e:
        logger.error(f"Error in offer_score_post_save: {e}")


@receiver(post_save, sender=UserPreferenceVector)
def preference_vector_post_save(sender, instance, **kwargs):
    """
    Handle post-save signal for UserPreferenceVector.
    Triggers personalization updates.
    """
    try:
        logger.debug(f"Preference vector saved: {instance.id} for user {instance.user_id}")
        
        # Update preference cache
        if instance.user_id:
            cache_service.set_preference_vector(
                user_id=instance.user_id,
                preference_vector=instance.vector
            )
        
        # Update personalization analytics
        from .tasks.analytics import update_personalization_analytics
        update_personalization_analytics.delay(
            user_id=instance.user_id,
            preference_id=instance.id
        )
        
        # Clear routing cache for this user
        cache_keys = [
            f"routing:user_{instance.user_id}:*",
            f"personalization:user_{instance.user_id}:*",
            f"affinity_scores:user_{instance.user_id}:*"
        ]
        cache_service.delete_multiple(cache_keys)
        
        logger.debug(f"Post-save processing for preference vector {instance.id}")
        
    except Exception as e:
        logger.error(f"Error in preference_vector_post_save: {e}")


# Delete signals
@receiver(post_delete, sender=RoutingDecisionLog)
def routing_decision_post_delete(sender, instance, **kwargs):
    """
    Handle post-delete signal for RoutingDecisionLog.
    Triggers analytics cleanup.
    """
    try:
        logger.info(f"Routing decision deleted: {instance.id}")
        
        # Update analytics
        from .tasks.analytics import cleanup_decision_analytics
        cleanup_decision_analytics.delay(
            decision_id=instance.id,
            user_id=instance.user_id
        )
        
    except Exception as e:
        logger.error(f"Error in routing_decision_post_delete: {e}")


@receiver(post_delete, sender=OfferRoutingCap)
def routing_cap_post_delete(sender, instance, **kwargs):
    """
    Handle post-delete signal for OfferRoutingCap.
    Triggers cache cleanup.
    """
    try:
        logger.info(f"Routing cap deleted: {instance.id}")
        
        # Clear related cache
        if instance.offer_id:
            cache_keys = [
                f"routing:offer_{instance.offer_id}:*",
                f"global_caps:offer_{instance.offer_id}",
                f"cap_analytics:offer_{instance.offer_id}"
            ]
            cache_service.delete_multiple(cache_keys)
        
    except Exception as e:
        logger.error(f"Error in routing_cap_post_delete: {e}")


@receiver(post_delete, sender=UserOfferCap)
def user_cap_post_delete(sender, instance, **kwargs):
    """
    Handle post-delete signal for UserOfferCap.
    Triggers user cache cleanup.
    """
    try:
        logger.info(f"User cap deleted: {instance.id}")
        
        # Clear user-specific cache
        if instance.user_id:
            cache_keys = [
                f"user_caps:user_{instance.user_id}:*",
                f"routing:user_{instance.user_id}:*"
            ]
            cache_service.delete_multiple(cache_keys)
        
    except Exception as e:
        logger.error(f"Error in user_cap_post_delete: {e}")


# Bulk operation signals
# DISABLED: was connected to post_save but reads kwargs updates/tenant_id, which post_save never sends (silent no-op on every save). Wire it to a bulk-update signal if one exists.
def bulk_routing_update(sender, **kwargs):
    """
    Handle bulk routing updates.
    Optimizes cache operations for multiple updates.
    """
    try:
        updates = kwargs.get('updates', [])
        tenant_id = kwargs.get('tenant_id')
        
        if updates and tenant_id:
            logger.info(f"Bulk routing update: {len(updates)} updates for tenant {tenant_id}")
            
            # Clear all routing cache for tenant
            cache_keys = [
                f"routing:tenant_{tenant_id}:*",
                f"scoring:tenant_{tenant_id}:*",
                f"personalization:tenant_{tenant_id}:*"
            ]
            cache_service.delete_multiple(cache_keys)
            
            # Schedule bulk analytics update
            from .tasks.analytics import bulk_update_analytics
            bulk_update_analytics.delay(
                tenant_id=tenant_id,
                updates=updates
            )
        
    except Exception as e:
        logger.error(f"Error in bulk_routing_update: {e}")


# Utility functions for signal handling
def disconnect_signals():
    """
    Disconnect all routing signals for testing.
    """
    from django.db.models.signals import post_save, pre_save, post_delete
    
    signals_to_disconnect = [
        (routing_decision_pre_save, post_save),
        (routing_decision_post_save, post_save),
        (routing_cap_pre_save, post_save),
        (routing_cap_post_save, post_save),
        (routing_config_post_save, post_save),
        (user_cap_pre_save, post_save),
        (user_cap_post_save, post_save),
        (ab_test_post_save, post_save),
        (performance_stat_post_save, post_save),
        (offer_history_post_save, post_save),
        (offer_score_post_save, post_save),
        (preference_vector_post_save, post_save),
        (routing_decision_post_delete, post_delete),
        (routing_cap_post_delete, post_delete),
        (user_cap_post_delete, post_delete),
    ]
    
    for handler, signal in signals_to_disconnect:
        signal.disconnect(handler)
    
    logger.info("All routing signals disconnected")


def connect_signals():
    """
    Connect all routing signals.
    """
    logger.info("All routing signals connected")
from django.dispatch import Signal

# Performance monitoring signals
performance_alert = Signal()


# Route lifecycle signals
route_created = Signal()
route_updated = Signal()
route_deleted = Signal()
route_activated = Signal()
route_deactivated = Signal()

# Decision signals
routing_decision_made = Signal()
routing_decision_cached = Signal()

# Cap signals
cap_exceeded = Signal()
cap_reset = Signal()

# A/B test signals
ab_test_started = Signal()
ab_test_completed = Signal()
ab_test_winner_selected = Signal()
ab_test_winner = ab_test_winner_selected
ab_test_assignment = ab_test_assignment_made if 'ab_test_assignment_made' in dir() else Signal()

# Auto-added missing signals
from django.dispatch import Signal
offer_score_updated = Signal()
offer_score_created = Signal()
cap_threshold_reached = Signal()
personalization_updated = Signal()
ab_test_assignment_made = Signal()
route_performance_updated = Signal()
fallback_triggered = Signal()
fraud_detected = Signal()
postback_received = Signal()
postback_processed = Signal()
cap_limit_reached = Signal()
cap_warning_threshold_reached = Signal()
user_cap_exceeded = Signal()
performance_threshold_exceeded = Signal()
system_health_degraded = Signal()

# ─────────────────────────────────────────────────────────────────────────────
# ABTest signals
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender=ABTestAssignment)
def ab_test_assignment_post_save(sender, instance, created, **kwargs):
    """Invalidate AB test stats cache when a new assignment is created."""
    if not created:
        return
    try:
        from .services.cache import cache_service
        cache_service.clear_pattern(f'ab_test:stats:{instance.test_id}:*')
        logger.debug("AB test assignment cache cleared for test %s", instance.test_id)
    except Exception as e:
        logger.error("ab_test_assignment_post_save error: %s", e)


@receiver(post_save, sender=ABTestResult)
def ab_test_result_post_save(sender, instance, created, **kwargs):
    """Invalidate AB test results cache when a new result event is recorded."""
    if not created:
        return
    try:
        from .services.cache import cache_service
        cache_service.clear_pattern(f'ab_test:results:{instance.test_id}:*')
        logger.debug("AB test result cache cleared for test %s", instance.test_id)
    except Exception as e:
        logger.error("ab_test_result_post_save error: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# Fallback signals
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender=FallbackRule)
def fallback_rule_post_save(sender, instance, created, **kwargs):
    """Invalidate fallback cache when a rule is created or updated."""
    try:
        from .services.cache import cache_service
        cache_service.clear_pattern(f'fallback:rules:*')
        logger.debug("Fallback rule cache invalidated for rule %s", instance.id)
    except Exception as e:
        logger.error("fallback_rule_post_save error: %s", e)


@receiver(post_delete, sender=FallbackRule)
def fallback_rule_post_delete(sender, instance, **kwargs):
    """Invalidate fallback cache when a rule is deleted."""
    try:
        from .services.cache import cache_service
        cache_service.clear_pattern(f'fallback:rules:*')
        logger.debug("Fallback rule deleted: %s", instance.id)
    except Exception as e:
        logger.error("fallback_rule_post_delete error: %s", e)


@receiver(post_save, sender=DefaultOfferPool)
def default_offer_pool_post_save(sender, instance, created, **kwargs):
    """Invalidate fallback pool cache when pool is updated."""
    try:
        from .services.cache import cache_service
        cache_service.clear_pattern(f'fallback:pool:{instance.id}:*')
        logger.debug("Default offer pool cache cleared: %s", instance.id)
    except Exception as e:
        logger.error("default_offer_pool_post_save error: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# Geo targeting signals
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender=GeoRouteRule)
def geo_route_rule_post_save(sender, instance, created, **kwargs):
    """Invalidate geo targeting cache when a rule is updated."""
    try:
        from .services.cache import cache_service
        cache_service.clear_pattern(f'geo:rules:*')
        logger.debug("Geo route rule cache cleared for rule %s", instance.id)
    except Exception as e:
        logger.error("geo_route_rule_post_save error: %s", e)


@receiver(post_delete, sender=GeoRouteRule)
def geo_route_rule_post_delete(sender, instance, **kwargs):
    """Invalidate geo targeting cache when a rule is deleted."""
    try:
        from .services.cache import cache_service
        cache_service.clear_pattern(f'geo:rules:*')
        logger.debug("Geo route rule deleted: %s", instance.id)
    except Exception as e:
        logger.error("geo_route_rule_post_delete error: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# CapOverride signals
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender=CapOverride)
def cap_override_post_save(sender, instance, created, **kwargs):
    """Invalidate cap cache when an override is created or changed."""
    try:
        from .services.cache import cache_service
        user_id = getattr(instance, 'user_id', None)
        if user_id:
            cache_service.clear_pattern(f'user_cap:*:{user_id}')
        logger.debug("Cap override cache cleared for user %s", user_id)
    except Exception as e:
        logger.error("cap_override_post_save error: %s", e)


@receiver(post_delete, sender=CapOverride)
def cap_override_post_delete(sender, instance, **kwargs):
    """Invalidate cap override cache on delete."""
    try:
        from .services.cache import cache_service
        user_id = getattr(instance, 'user_id', None)
        if user_id:
            cache_service.clear_pattern(f'user_cap:*:{user_id}')
        logger.debug("Cap override deleted for user %s", user_id)
    except Exception as e:
        logger.error("cap_override_post_delete error: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# OfferRoute signals
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender=OfferRoute)
def offer_route_post_save(sender, instance, created, **kwargs):
    """Invalidate route cache and re-score on update."""
    try:
        from .services.cache import cache_service
        cache_service.clear_pattern(f'routing:route:{instance.id}:*')
        logger.debug("OfferRoute cache cleared for route %s", instance.id)
    except Exception as e:
        logger.error("offer_route_post_save error: %s", e)


@receiver(post_delete, sender=OfferRoute)
def offer_route_post_delete(sender, instance, **kwargs):
    """Clean up cache entries when a route is deleted."""
    try:
        from .services.cache import cache_service
        cache_service.clear_pattern(f'routing:route:{instance.id}:*')
        cache_service.clear_pattern(f'score:{instance.id}:*')
        logger.debug("OfferRoute deleted and cache cleared: %s", instance.id)
    except Exception as e:
        logger.error("offer_route_post_delete error: %s", e)

