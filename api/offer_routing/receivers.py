"""
Signal Receivers for Offer Routing System

This module contains signal receivers that handle various events
in the offer routing system, including model signals, user signals,
and custom business logic signals.
"""

import logging
from typing import Dict, Any, Optional
from django.db.models.signals import post_save, post_delete, pre_save, pre_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings

from .models import (
    OfferRoute, RouteCondition, RouteAction, OfferScore, UserOfferHistory,
    RoutingDecisionLog, RoutingInsight, OfferRoutingCap, UserOfferCap,
    RoutingABTest, ABTestAssignment, NetworkPerformanceCache
)
from .signals import (
    route_created, route_updated, route_deleted,
    offer_score_updated, routing_decision_made,
    cap_limit_reached, ab_test_completed, performance_alert
)
from .tasks import (
    update_offer_scores_task, cleanup_routing_logs_task,
    send_notification_task, update_routing_cache_task
)

logger = logging.getLogger(__name__)
User = get_user_model()


# Model Signal Receivers

@receiver(pre_save, sender=OfferRoute)
def offer_route_pre_save(sender, instance, **kwargs):
    """Handle pre-save operations for OfferRoute."""
    try:
        # Validate route configuration
        if instance.is_active and not instance.name:
            raise ValueError("Active routes must have a name")
        
        # Set defaults
        if not instance.priority:
            instance.priority = 50
        
        if not instance.status:
            instance.status = 'draft'
        
        logger.debug(f"Pre-save processing for OfferRoute: {instance.name}")
        
    except Exception as e:
        logger.error(f"Error in offer_route_pre_save: {str(e)}")
        raise


@receiver(post_save, sender=OfferRoute)
def offer_route_post_save(sender, instance, created, **kwargs):
    """Handle post-save operations for OfferRoute."""
    try:
        if created:
            logger.info(f"New OfferRoute created: {instance.name}")
            # Send custom signal
            route_created.send(
                sender=sender,
                route_id=instance.id,
                route_name=instance.name,
                created_by=getattr(instance, 'created_by', None)
            )
            
            # Initialize default conditions if none exist
            if not instance.conditions.exists():
                create_default_conditions(instance)
        else:
            logger.info(f"OfferRoute updated: {instance.name}")
            # Send custom signal
            route_updated.send(
                sender=sender,
                route_id=instance.id,
                route_name=instance.name,
                changes=get_model_changes(instance)
            )
        
        # Update cache
        update_routing_cache_task.delay(instance.id)
        
        # Log activity
        log_route_activity(instance, 'created' if created else 'updated')
        
    except Exception as e:
        logger.error(f"Error in offer_route_post_save: {str(e)}")


@receiver(pre_delete, sender=OfferRoute)
def offer_route_pre_delete(sender, instance, **kwargs):
    """Handle pre-delete operations for OfferRoute."""
    try:
        # Check if route can be deleted
        if instance.is_active and instance.routingdecisionlog_set.exists():
            logger.warning(f"Deleting active route with history: {instance.name}")
        
        # Archive routing logs before deletion
        archive_route_logs(instance)
        
    except Exception as e:
        logger.error(f"Error in offer_route_pre_delete: {str(e)}")


@receiver(post_delete, sender=OfferRoute)
def offer_route_post_delete(sender, instance, **kwargs):
    """Handle post-delete operations for OfferRoute."""
    try:
        logger.info(f"OfferRoute deleted: {instance.name}")
        
        # Send custom signal
        route_deleted.send(
            sender=sender,
            route_id=instance.id,
            route_name=instance.name,
            deleted_by=getattr(instance, 'deleted_by', None)
        )
        
        # Clear cache
        cache.delete(f"route_config:{instance.id}")
        
    except Exception as e:
        logger.error(f"Error in offer_route_post_delete: {str(e)}")


@receiver(post_save, sender=OfferScore)
def offer_score_post_save(sender, instance, created, **kwargs):
    """Handle post-save operations for OfferScore."""
    try:
        if created:
            logger.info(f"New OfferScore created for user {instance.user_id}, offer {instance.offer_id}")
        else:
            logger.info(f"OfferScore updated for user {instance.user_id}, offer {instance.offer_id}")
        
        # Send custom signal
        offer_score_updated.send(
            sender=sender,
            user_id=instance.user_id,
            offer_id=instance.offer_id,
            score=instance.score,
            created=created
        )
        
        # Update related caches
        cache.delete(f"user_scores:{instance.user_id}")
        cache.delete(f"offer_scores:{instance.offer_id}")
        
        # Trigger async task for score updates
        update_offer_scores_task.delay(instance.offer_id)
        
    except Exception as e:
        logger.error(f"Error in offer_score_post_save: {str(e)}")


@receiver(post_save, sender=UserOfferHistory)
def user_offer_history_post_save(sender, instance, created, **kwargs):
    """Handle post-save operations for UserOfferHistory."""
    try:
        if created:
            logger.info(f"New UserOfferHistory created: user {instance.user_id}, offer {instance.offer_id}")
            
            # Update user interaction stats
            update_user_interaction_stats(instance.user_id)
            
            # Update offer performance stats
            update_offer_performance_stats(instance.offer_id)
            
            # Check caps
            check_offer_caps(instance.user_id, instance.offer_id)
        
    except Exception as e:
        logger.error(f"Error in user_offer_history_post_save: {str(e)}")


@receiver(post_save, sender=RoutingDecisionLog)
def routing_decision_log_post_save(sender, instance, created, **kwargs):
    """Handle post-save operations for RoutingDecisionLog."""
    try:
        if created:
            logger.info(f"Routing decision logged: user {instance.user_id}, route {instance.route_id}")
            
            # Send custom signal
            routing_decision_made.send(
                sender=sender,
                user_id=instance.user_id,
                route_id=instance.route_id,
                success=instance.success,
                response_time=instance.response_time,
                score=instance.score
            )
            
            # Update performance metrics
            update_route_performance_metrics(instance.route_id)
            
            # Check for performance alerts
            check_performance_alerts(instance)
        
    except Exception as e:
        logger.error(f"Error in routing_decision_log_post_save: {str(e)}")


@receiver(post_save, sender=OfferRoutingCap)
def offer_routing_cap_post_save(sender, instance, created, **kwargs):
    """Handle post-save operations for OfferRoutingCap."""
    try:
        if created:
            logger.info(f"New OfferRoutingCap created: offer {instance.offer_id}, type {instance.cap_type}")
        
        # Update cache
        cache.delete(f"offer_caps:{instance.offer_id}")
        
        # Check if cap is reached
        if instance.is_limit_reached():
            cap_limit_reached.send(
                sender=sender,
                offer_id=instance.offer_id,
                cap_type=instance.cap_type,
                current_count=instance.current_count,
                max_count=instance.max_count
            )
        
    except Exception as e:
        logger.error(f"Error in offer_routing_cap_post_save: {str(e)}")


@receiver(post_save, sender=UserOfferCap)
def user_offer_cap_post_save(sender, instance, created, **kwargs):
    """Handle post-save operations for UserOfferCap."""
    try:
        if created:
            logger.info(f"New UserOfferCap created: user {instance.user_id}, offer {instance.offer_id}")
        
        # Update cache
        cache.delete(f"user_caps:{instance.user_id}")
        
        # Check if cap is reached
        if instance.is_limit_reached():
            cap_limit_reached.send(
                sender=sender,
                user_id=instance.user_id,
                offer_id=instance.offer_id,
                cap_type=instance.cap_type,
                current_count=instance.current_count,
                max_count=instance.max_count
            )
        
    except Exception as e:
        logger.error(f"Error in user_offer_cap_post_save: {str(e)}")


@receiver(post_save, sender=RoutingABTest)
def routing_ab_test_post_save(sender, instance, created, **kwargs):
    """Handle post-save operations for RoutingABTest."""
    try:
        if created:
            logger.info(f"New RoutingABTest created: {instance.name}")
        
        # Update cache
        cache.delete(f"ab_tests:{instance.route_id}")
        
        # Check if test is completed
        if instance.status == 'completed':
            ab_test_completed.send(
                sender=sender,
                test_id=instance.id,
                test_name=instance.name,
                winning_variant=instance.winning_variant,
                confidence_level=instance.confidence_level
            )
        
    except Exception as e:
        logger.error(f"Error in routing_ab_test_post_save: {str(e)}")


@receiver(post_save, sender=ABTestAssignment)
def ab_test_assignment_post_save(sender, instance, created, **kwargs):
    """Handle post-save operations for ABTestAssignment."""
    try:
        if created:
            logger.info(f"New ABTestAssignment created: user {instance.user_id}, test {instance.test_id}")
        
        # Update test statistics
        update_ab_test_statistics(instance.test_id)
        
    except Exception as e:
        logger.error(f"Error in ab_test_assignment_post_save: {str(e)}")


# Custom Signal Receivers

@receiver(route_created)
def handle_route_created(sender, route_id: int, route_name: str, **kwargs):
    """Handle route creation signal."""
    try:
        logger.info(f"Handling route creation: {route_name} (ID: {route_id})")
        
        # Send notification
        send_notification_task.delay(
            notification_type='route_created',
            message=f"New route '{route_name}' has been created",
            data={'route_id': route_id, 'route_name': route_name}
        )
        
        # Initialize performance tracking
        initialize_performance_tracking(route_id)
        
    except Exception as e:
        logger.error(f"Error handling route_created signal: {str(e)}")


@receiver(route_updated)
def handle_route_updated(sender, route_id: int, route_name: str, changes: Dict[str, Any], **kwargs):
    """Handle route update signal."""
    try:
        logger.info(f"Handling route update: {route_name} (ID: {route_id})")
        
        # Send notification for important changes
        important_changes = ['status', 'is_active', 'priority']
        if any(change in changes for change in important_changes):
            send_notification_task.delay(
                notification_type='route_updated',
                message=f"Route '{route_name}' has been updated",
                data={'route_id': route_id, 'route_name': route_name, 'changes': changes}
            )
        
        # Rebuild routing cache
        rebuild_routing_cache(route_id)
        
    except Exception as e:
        logger.error(f"Error handling route_updated signal: {str(e)}")


@receiver(route_deleted)
def handle_route_deleted(sender, route_id: int, route_name: str, **kwargs):
    """Handle route deletion signal."""
    try:
        logger.info(f"Handling route deletion: {route_name} (ID: {route_id})")
        
        # Send notification
        send_notification_task.delay(
            notification_type='route_deleted',
            message=f"Route '{route_name}' has been deleted",
            data={'route_id': route_id, 'route_name': route_name}
        )
        
        # Clean up related data
        cleanup_route_related_data(route_id)
        
    except Exception as e:
        logger.error(f"Error handling route_deleted signal: {str(e)}")


@receiver(offer_score_updated)
def handle_offer_score_updated(sender, user_id: int, offer_id: int, score: float, **kwargs):
    """Handle offer score update signal."""
    try:
        logger.info(f"Handling offer score update: user {user_id}, offer {offer_id}, score {score}")
        
        # Update user preference vectors
        update_user_preference_vectors(user_id)
        
        # Update offer rankings
        update_offer_rankings(offer_id)
        
        # Check for significant score changes
        check_score_changes(user_id, offer_id, score)
        
    except Exception as e:
        logger.error(f"Error handling offer_score_updated signal: {str(e)}")


@receiver(routing_decision_made)
def handle_routing_decision_made(sender, user_id: int, route_id: int, success: bool, **kwargs):
    """Handle routing decision signal."""
    try:
        logger.info(f"Handling routing decision: user {user_id}, route {route_id}, success {success}")
        
        # Update user journey
        update_user_journey(user_id, route_id, success)
        
        # Update route performance
        update_route_performance(route_id, success)
        
        # Check for performance alerts
        if not success:
            check_routing_errors(user_id, route_id)
        
    except Exception as e:
        logger.error(f"Error handling routing_decision_made signal: {str(e)}")


@receiver(cap_limit_reached)
def handle_cap_limit_reached(sender, **kwargs):
    """Handle cap limit reached signal."""
    try:
        logger.info(f"Cap limit reached: {kwargs}")
        
        # Send alert notification
        send_notification_task.delay(
            notification_type='cap_limit_reached',
            message="Offer cap limit has been reached",
            data=kwargs
        )
        
        # Pause offer if needed
        if kwargs.get('auto_pause', False):
            pause_offer(kwargs.get('offer_id'))
        
    except Exception as e:
        logger.error(f"Error handling cap_limit_reached signal: {str(e)}")


@receiver(ab_test_completed)
def handle_ab_test_completed(sender, test_id: int, test_name: str, **kwargs):
    """Handle A/B test completion signal."""
    try:
        logger.info(f"Handling A/B test completion: {test_name} (ID: {test_id})")
        
        # Send notification
        send_notification_task.delay(
            notification_type='ab_test_completed',
            message=f"A/B test '{test_name}' has been completed",
            data={'test_id': test_id, 'test_name': test_name, **kwargs}
        )
        
        # Apply winning variant
        if kwargs.get('winning_variant'):
            apply_winning_variant(test_id, kwargs['winning_variant'])
        
        # Generate insights
        generate_ab_test_insights(test_id)
        
    except Exception as e:
        logger.error(f"Error handling ab_test_completed signal: {str(e)}")


@receiver(performance_alert)
def handle_performance_alert(sender, alert_type: str, data: Dict[str, Any], **kwargs):
    """Handle performance alert signal."""
    try:
        logger.info(f"Handling performance alert: {alert_type}")
        
        # Send alert notification
        send_notification_task.delay(
            notification_type='performance_alert',
            message=f"Performance alert: {alert_type}",
            data={'alert_type': alert_type, **data}
        )
        
        # Take automatic action if configured
        if alert_type in ['high_error_rate', 'slow_response_time']:
            take_automatic_action(alert_type, data)
        
    except Exception as e:
        logger.error(f"Error handling performance_alert signal: {str(e)}")


# User Signal Receivers

@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    """Handle user creation/update."""
    try:
        if created:
            logger.info(f"New user created: {instance.username}")
            
            # Initialize user preferences
            initialize_user_preferences(instance.id)
            
            # Create default caps
            create_default_user_caps(instance.id)
        
        # Update user cache
        cache.delete(f"user_profile:{instance.id}")
        
    except Exception as e:
        logger.error(f"Error in user_post_save: {str(e)}")


# Utility Functions

def create_default_conditions(route):
    """Create default conditions for a new route."""
    from .models import RouteCondition
    
    default_conditions = [
        {
            'field_name': 'user_status',
            'operator': 'equals',
            'value': 'active',
            'priority': 1
        },
        {
            'field_name': 'offer_status',
            'operator': 'equals',
            'value': 'active',
            'priority': 2
        }
    ]
    
    for condition_data in default_conditions:
        RouteCondition.objects.create(
            route=route,
            **condition_data
        )


def get_model_changes(instance):
    """Get model changes for logging."""
    if hasattr(instance, '_original_values'):
        changes = {}
        for field, original_value in instance._original_values.items():
            current_value = getattr(instance, field)
            if original_value != current_value:
                changes[field] = {
                    'from': original_value,
                    'to': current_value
                }
        return changes
    return {}


def log_route_activity(route, action):
    """Log route activity."""
    from .models import RoutingActivityLog
    
    RoutingActivityLog.objects.create(
        route=route,
        action=action,
        user=getattr(route, 'modified_by', None),
        timestamp=timezone.now()
    )


def archive_route_logs(route):
    """Archive routing logs before route deletion."""
    # Implementation for archiving logs
    pass


def update_user_interaction_stats(user_id):
    """Update user interaction statistics."""
    # Implementation for updating stats
    pass


def update_offer_performance_stats(offer_id):
    """Update offer performance statistics."""
    # Implementation for updating stats
    pass


def check_offer_caps(user_id, offer_id):
    """Check if caps are reached."""
    # Implementation for checking caps
    pass


def update_route_performance_metrics(route_id):
    """Update route performance metrics."""
    # Implementation for updating metrics
    pass


def check_performance_alerts(log_entry):
    """Check for performance alerts."""
    # Implementation for checking alerts
    pass


def update_ab_test_statistics(test_id):
    """Update A/B test statistics."""
    # Implementation for updating stats
    pass


def initialize_performance_tracking(route_id):
    """Initialize performance tracking for a route."""
    # Implementation for initialization
    pass


def rebuild_routing_cache(route_id):
    """Rebuild routing cache for a route."""
    # Implementation for cache rebuild
    pass


def cleanup_route_related_data(route_id):
    """Clean up data related to a deleted route."""
    # Implementation for cleanup
    pass


def update_user_preference_vectors(user_id):
    """Update user preference vectors."""
    # Implementation for updating vectors
    pass


def update_offer_rankings(offer_id):
    """Update offer rankings."""
    # Implementation for updating rankings
    pass


def check_score_changes(user_id, offer_id, score):
    """Check for significant score changes."""
    # Implementation for checking changes
    pass


def update_user_journey(user_id, route_id, success):
    """Update user journey."""
    # Implementation for updating journey
    pass


def update_route_performance(route_id, success):
    """Update route performance."""
    # Implementation for updating performance
    pass


def check_routing_errors(user_id, route_id):
    """Check for routing errors."""
    # Implementation for error checking
    pass


def pause_offer(offer_id):
    """Pause an offer."""
    # Implementation for pausing offer
    pass


def apply_winning_variant(test_id, winning_variant):
    """Apply winning variant from A/B test."""
    # Implementation for applying variant
    pass


def generate_ab_test_insights(test_id):
    """Generate insights from A/B test."""
    # Implementation for generating insights
    pass


def take_automatic_action(alert_type, data):
    """Take automatic action for alerts."""
    # Implementation for automatic actions
    pass


def initialize_user_preferences(user_id):
    """Initialize user preferences."""
    # Implementation for initialization
    pass


def create_default_user_caps(user_id):
    """Create default user caps."""
    # Implementation for creating caps
    pass


# Export the receiver functions
__all__ = [
    'offer_route_pre_save',
    'offer_route_post_save',
    'offer_route_pre_delete',
    'offer_route_post_delete',
    'offer_score_post_save',
    'user_offer_history_post_save',
    'routing_decision_log_post_save',
    'offer_routing_cap_post_save',
    'user_offer_cap_post_save',
    'routing_ab_test_post_save',
    'ab_test_assignment_post_save',
    'handle_route_created',
    'handle_route_updated',
    'handle_route_deleted',
    'handle_offer_score_updated',
    'handle_routing_decision_made',
    'handle_cap_limit_reached',
    'handle_ab_test_completed',
    'handle_performance_alert',
    'user_post_save',
]
