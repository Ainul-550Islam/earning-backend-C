"""Event Router Service

This module provides event routing to matching webhook subscriptions.
"""

import logging
from typing import Dict, Any, Optional, List
from django.db import transaction
from django.utils import timezone

from ...models import WebhookSubscription, WebhookEndpoint
from ...choices import WebhookStatus

logger = logging.getLogger(__name__)


class EventRouter:
    """Service for routing webhook events to matching subscriptions."""
    
    def __init__(self):
        """Initialize the event router service."""
        self.logger = logger
    
    def route_event(self, event_type: str, payload: Dict[str, Any], user_id: Optional[str] = None) -> List[WebhookSubscription]:
        """
        Route an event to matching subscriptions.
        
        Args:
            event_type: The type of event to route
            payload: Event payload data
            user_id: Optional user ID to filter subscriptions
            
        Returns:
            List of matching subscriptions
        """
        try:
            # Get base queryset for subscriptions
            subscriptions = WebhookSubscription.objects.filter(
                event_type=event_type,
                is_active=True,
                endpoint__status=WebhookStatus.ACTIVE
            ).select_related('endpoint')
            
            # Filter by user if specified
            if user_id:
                subscriptions = subscriptions.filter(endpoint__owner_id=user_id)
            
            # Apply filtering to get matching subscriptions
            matching_subscriptions = []
            
            for subscription in subscriptions:
                if self._should_route_to_subscription(subscription, payload):
                    matching_subscriptions.append(subscription)
            
            self.logger.info(
                f"Event {event_type} routed to {len(matching_subscriptions)} subscriptions"
            )
            
            return matching_subscriptions
            
        except Exception as e:
            logger.error(f"Error routing event {event_type}: {str(e)}")
            return []
    
    def route_event_to_endpoints(self, event_type: str, payload: Dict[str, Any], endpoint_ids: List[str]) -> List[WebhookSubscription]:
        """
        Route an event to specific endpoints.
        
        Args:
            event_type: The type of event to route
            payload: Event payload data
            endpoint_ids: List of endpoint IDs to route to
            
        Returns:
            List of matching subscriptions
        """
        try:
            # Get subscriptions for specific endpoints
            subscriptions = WebhookSubscription.objects.filter(
                event_type=event_type,
                is_active=True,
                endpoint__status=WebhookStatus.ACTIVE,
                endpoint__id__in=endpoint_ids
            ).select_related('endpoint')
            
            # Apply filtering to get matching subscriptions
            matching_subscriptions = []
            
            for subscription in subscriptions:
                if self._should_route_to_subscription(subscription, payload):
                    matching_subscriptions.append(subscription)
            
            self.logger.info(
                f"Event {event_type} routed to {len(matching_subscriptions)} specific subscriptions"
            )
            
            return matching_subscriptions
            
        except Exception as e:
            logger.error(f"Error routing event {event_type} to endpoints: {str(e)}")
            return []
    
    def _should_route_to_subscription(self, subscription: WebhookSubscription, payload: Dict[str, Any]) -> bool:
        """
        Check if event should be routed to subscription based on filters.
        
        Args:
            subscription: The subscription to check
            payload: Event payload data
            
        Returns:
            True if event should be routed, False otherwise
        """
        try:
            # If no filter config, route to all
            if not subscription.filter_config:
                return True
            
            # Apply filters
            from .FilterService import FilterService
            filter_service = FilterService()
            
            return filter_service.evaluate_filter_config(subscription.filter_config, payload)
            
        except Exception as e:
            logger.error(f"Error evaluating subscription filter: {str(e)}")
            # If filter evaluation fails, route to be safe
            return True
    
    def get_routing_statistics(self, event_type: str = None, days: int = 7) -> Dict[str, Any]:
        """
        Get routing statistics for events.
        
        Args:
            event_type: Optional event type to filter by
            days: Number of days to look back
            
        Returns:
            Dictionary with routing statistics
        """
        try:
            from datetime import timedelta
            from django.db.models import Count, Q
            
            since = timezone.now() - timedelta(days=days)
            
            # Base query for subscriptions
            subscriptions = WebhookSubscription.objects.filter(
                is_active=True,
                endpoint__status=WebhookStatus.ACTIVE
            ).select_related('endpoint')
            
            if event_type:
                subscriptions = subscriptions.filter(event_type=event_type)
            
            # Get overall statistics
            total_subscriptions = subscriptions.count()
            
            # Get event type breakdown
            event_stats = subscriptions.values('event_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Get endpoint breakdown
            endpoint_stats = subscriptions.values(
                'endpoint__label',
                'endpoint__url'
            ).annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Get recent activity
            recent_subscriptions = subscriptions.filter(
                created_at__gte=since
            ).count()
            
            return {
                'total_subscriptions': total_subscriptions,
                'recent_subscriptions': recent_subscriptions,
                'event_type_breakdown': list(event_stats),
                'endpoint_breakdown': list(endpoint_stats),
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting routing statistics: {str(e)}")
            return {
                'total_subscriptions': 0,
                'recent_subscriptions': 0,
                'event_type_breakdown': [],
                'endpoint_breakdown': [],
                'period_days': days,
                'error': str(e)
            }
    
    def get_event_routing_map(self, event_type: str) -> Dict[str, Any]:
        """
        Get routing map for a specific event type.
        
        Args:
            event_type: The event type to map
            
        Returns:
            Dictionary with routing information
        """
        try:
            subscriptions = WebhookSubscription.objects.filter(
                event_type=event_type,
                is_active=True,
                endpoint__status=WebhookStatus.ACTIVE
            ).select_related('endpoint')
            
            routing_map = {
                'event_type': event_type,
                'total_subscriptions': subscriptions.count(),
                'endpoints': []
            }
            
            for subscription in subscriptions:
                endpoint_info = {
                    'endpoint_id': str(subscription.endpoint.id),
                    'endpoint_label': subscription.endpoint.label,
                    'endpoint_url': subscription.endpoint.url,
                    'subscription_id': str(subscription.id),
                    'has_filters': bool(subscription.filter_config),
                    'filter_config': subscription.filter_config if subscription.filter_config else None
                }
                routing_map['endpoints'].append(endpoint_info)
            
            return routing_map
            
        except Exception as e:
            logger.error(f"Error getting routing map for {event_type}: {str(e)}")
            return {
                'event_type': event_type,
                'total_subscriptions': 0,
                'endpoints': [],
                'error': str(e)
            }
    
    def get_user_routing_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get routing summary for a specific user.
        
        Args:
            user_id: The user ID to get summary for
            
        Returns:
            Dictionary with routing summary
        """
        try:
            subscriptions = WebhookSubscription.objects.filter(
                endpoint__owner_id=user_id,
                is_active=True,
                endpoint__status=WebhookStatus.ACTIVE
            ).select_related('endpoint')
            
            # Get event type breakdown
            event_stats = subscriptions.values('event_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Get endpoint breakdown
            endpoint_stats = subscriptions.values(
                'endpoint__label',
                'endpoint__url'
            ).annotate(
                count=Count('id')
            ).order_by('-count')
            
            return {
                'user_id': user_id,
                'total_subscriptions': subscriptions.count(),
                'event_type_breakdown': list(event_stats),
                'endpoint_breakdown': list(endpoint_stats)
            }
            
        except Exception as e:
            logger.error(f"Error getting routing summary for user {user_id}: {str(e)}")
            return {
                'user_id': user_id,
                'total_subscriptions': 0,
                'event_type_breakdown': [],
                'endpoint_breakdown': [],
                'error': str(e)
            }
    
    def find_orphaned_subscriptions(self) -> List[Dict[str, Any]]:
        """
        Find subscriptions that might be orphaned (no recent events).
        
        Returns:
            List of potentially orphaned subscriptions
        """
        try:
            from datetime import timedelta
            from ...models import WebhookDeliveryLog
            
            # Get all active subscriptions
            subscriptions = WebhookSubscription.objects.filter(
                is_active=True,
                endpoint__status=WebhookStatus.ACTIVE
            ).select_related('endpoint')
            
            orphaned = []
            
            for subscription in subscriptions:
                # Check for recent deliveries
                recent_deliveries = WebhookDeliveryLog.objects.filter(
                    endpoint=subscription.endpoint,
                    event_type=subscription.event_type,
                    created_at__gte=timezone.now() - timedelta(days=30)
                ).count()
                
                if recent_deliveries == 0:
                    orphaned.append({
                        'subscription_id': str(subscription.id),
                        'event_type': subscription.event_type,
                        'endpoint_id': str(subscription.endpoint.id),
                        'endpoint_label': subscription.endpoint.label,
                        'endpoint_url': subscription.endpoint.url,
                        'last_delivery': None
                    })
                else:
                    # Get last delivery time
                    last_delivery = WebhookDeliveryLog.objects.filter(
                        endpoint=subscription.endpoint,
                        event_type=subscription.event_type
                    ).order_by('-created_at').first()
                    
                    if last_delivery:
                        days_since_last = (timezone.now() - last_delivery.created_at).days
                        if days_since_last > 30:
                            orphaned.append({
                                'subscription_id': str(subscription.id),
                                'event_type': subscription.event_type,
                                'endpoint_id': str(subscription.endpoint.id),
                                'endpoint_label': subscription.endpoint.label,
                                'endpoint_url': subscription.endpoint.url,
                                'last_delivery': last_delivery.created_at.isoformat(),
                                'days_since_last': days_since_last
                            })
            
            return orphaned
            
        except Exception as e:
            logger.error(f"Error finding orphaned subscriptions: {str(e)}")
            return []
    
    def validate_routing_configuration(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate routing configuration for an event type.
        
        Args:
            event_type: The event type to validate
            payload: Sample payload for validation
            
        Returns:
            Dictionary with validation results
        """
        try:
            subscriptions = WebhookSubscription.objects.filter(
                event_type=event_type,
                is_active=True,
                endpoint__status=WebhookStatus.ACTIVE
            ).select_related('endpoint')
            
            validation_results = {
                'event_type': event_type,
                'total_subscriptions': subscriptions.count(),
                'valid_subscriptions': 0,
                'invalid_subscriptions': 0,
                'subscription_results': []
            }
            
            for subscription in subscriptions:
                try:
                    # Test filter evaluation
                    should_route = self._should_route_to_subscription(subscription, payload)
                    
                    if should_route:
                        validation_results['valid_subscriptions'] += 1
                    else:
                        validation_results['invalid_subscriptions'] += 1
                    
                    validation_results['subscription_results'].append({
                        'subscription_id': str(subscription.id),
                        'endpoint_label': subscription.endpoint.label,
                        'endpoint_url': subscription.endpoint.url,
                        'has_filters': bool(subscription.filter_config),
                        'would_route': should_route
                    })
                    
                except Exception as e:
                    validation_results['invalid_subscriptions'] += 1
                    validation_results['subscription_results'].append({
                        'subscription_id': str(subscription.id),
                        'endpoint_label': subscription.endpoint.label,
                        'endpoint_url': subscription.endpoint.url,
                        'has_filters': bool(subscription.filter_config),
                        'would_route': False,
                        'error': str(e)
                    })
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating routing configuration: {str(e)}")
            return {
                'event_type': event_type,
                'total_subscriptions': 0,
                'valid_subscriptions': 0,
                'invalid_subscriptions': 0,
                'subscription_results': [],
                'error': str(e)
            }
    
    def get_event_type_subscriptions(self, event_type: str) -> List[Dict[str, Any]]:
        """
        Get all subscriptions for a specific event type.
        
        Args:
            event_type: The event type
            
        Returns:
            List of subscription information
        """
        try:
            subscriptions = WebhookSubscription.objects.filter(
                event_type=event_type,
                is_active=True,
                endpoint__status=WebhookStatus.ACTIVE
            ).select_related('endpoint')
            
            subscription_list = []
            
            for subscription in subscriptions:
                subscription_info = {
                    'subscription_id': str(subscription.id),
                    'endpoint_id': str(subscription.endpoint.id),
                    'endpoint_label': subscription.endpoint.label,
                    'endpoint_url': subscription.endpoint.url,
                    'endpoint_owner': subscription.endpoint.owner.username if subscription.endpoint.owner else None,
                    'has_filters': bool(subscription.filter_config),
                    'created_at': subscription.created_at.isoformat(),
                    'updated_at': subscription.updated_at.isoformat()
                }
                subscription_list.append(subscription_info)
            
            return subscription_list
            
        except Exception as e:
            logger.error(f"Error getting subscriptions for {event_type}: {str(e)}")
            return []
    
    def get_endpoint_subscriptions(self, endpoint_id: str) -> List[Dict[str, Any]]:
        """
        Get all subscriptions for a specific endpoint.
        
        Args:
            endpoint_id: The endpoint ID
            
        Returns:
            List of subscription information
        """
        try:
            subscriptions = WebhookSubscription.objects.filter(
                endpoint_id=endpoint_id,
                is_active=True,
                endpoint__status=WebhookStatus.ACTIVE
            )
            
            subscription_list = []
            
            for subscription in subscriptions:
                subscription_info = {
                    'subscription_id': str(subscription.id),
                    'event_type': subscription.event_type,
                    'has_filters': bool(subscription.filter_config),
                    'created_at': subscription.created_at.isoformat(),
                    'updated_at': subscription.updated_at.isoformat()
                }
                subscription_list.append(subscription_info)
            
            return subscription_list
            
        except Exception as e:
            logger.error(f"Error getting subscriptions for endpoint {endpoint_id}: {str(e)}")
            return []
