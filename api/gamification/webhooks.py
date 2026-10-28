"""
Gamification Webhooks — External webhook integration for gamification events.

This module handles webhook processing for external systems to receive
gamification event notifications and trigger automated workflows.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from api.gamification.models import WebhookEndpoint, WebhookDelivery, WebhookEvent
from api.gamification.choices import WebhookStatus, WebhookEventType
from api.gamification.exceptions import GamificationServiceError
from api.gamification.signals import (
    badge_earned, daily_challenge_completed, streak_updated,
    user_leveled_up, achievement_awarded
)

logger = logging.getLogger(__name__)


class WebhookManager:
    """Manager for handling gamification webhooks."""
    
    def __init__(self):
        self.timeout = getattr(settings, 'GAMIFICATION_WEBHOOK_TIMEOUT', 30)
        self.max_retries = getattr(settings, 'GAMIFICATION_WEBHOOK_MAX_RETRIES', 3)
        self.retry_delay = getattr(settings, 'GAMIFICATION_WEBHOOK_RETRY_DELAY', 60)
    
    def register_webhook(
        self,
        url: str,
        event_types: List[str],
        secret: Optional[str] = None,
        description: Optional[str] = None,
        is_active: bool = True,
        headers: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> WebhookEndpoint:
        """
        Register a new webhook endpoint.
        
        Args:
            url: Webhook URL
            event_types: List of event types to subscribe to
            secret: Optional secret for signature verification
            description: Optional description
            is_active: Whether the webhook is active
            headers: Optional custom headers
            metadata: Optional metadata
            
        Returns:
            WebhookEndpoint: Created webhook endpoint
            
        Raises:
            GamificationServiceError: If webhook registration fails
        """
        try:
            with transaction.atomic():
                # Validate event types
                valid_event_types = [event.value for event in WebhookEventType]
                for event_type in event_types:
                    if event_type not in valid_event_types:
                        raise ValidationError(f"Invalid event type: {event_type}")
                
                # Generate secret if not provided
                if not secret:
                    secret = self._generate_secret()
                
                # Create webhook endpoint
                webhook = WebhookEndpoint.objects.create(
                    url=url,
                    secret=secret,
                    description=description or "",
                    event_types=event_types,
                    is_active=is_active,
                    headers=headers or {},
                    metadata=metadata or {}
                )
                
                logger.info(f"Registered webhook {webhook.id} for events: {event_types}")
                return webhook
                
        except Exception as e:
            logger.error(f"Failed to register webhook: {e}")
            raise GamificationServiceError(f"Webhook registration failed: {e}")
    
    def trigger_webhook(
        self,
        event_type: str,
        data: Dict[str, Any],
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[WebhookDelivery]:
        """
        Trigger webhooks for a specific event.
        
        Args:
            event_type: Type of event
            data: Event data
            user_id: Optional user ID
            metadata: Optional metadata
            
        Returns:
            List[WebhookDelivery]: List of webhook deliveries
        """
        try:
            # Get active webhooks for this event type
            webhooks = WebhookEndpoint.objects.filter(
                is_active=True,
                event_types__icontains=[event_type]
            )
            
            if not webhooks.exists():
                logger.debug(f"No active webhooks for event type: {event_type}")
                return []
            
            deliveries = []
            
            with transaction.atomic():
                # Create webhook event record
                webhook_event = WebhookEvent.objects.create(
                    event_type=event_type,
                    data=data,
                    user_id=user_id,
                    metadata=metadata or {}
                )
                
                # Create deliveries for each webhook
                for webhook in webhooks:
                    delivery = WebhookDelivery.objects.create(
                        webhook=webhook,
                        event=webhook_event,
                        status=WebhookStatus.PENDING,
                        scheduled_at=timezone.now()
                    )
                    deliveries.append(delivery)
            
            # Process deliveries asynchronously
            for delivery in deliveries:
                self._process_webhook_delivery.delay(delivery.id)
            
            logger.info(f"Triggered {len(deliveries)} webhook deliveries for event: {event_type}")
            return deliveries
            
        except Exception as e:
            logger.error(f"Failed to trigger webhooks for event {event_type}: {e}")
            raise GamificationServiceError(f"Webhook trigger failed: {e}")
    
    def _process_webhook_delivery(self, delivery_id: str) -> bool:
        """
        Process a single webhook delivery.
        
        Args:
            delivery_id: Delivery ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            delivery = WebhookDelivery.objects.select_related('webhook', 'event').get(id=delivery_id)
            
            if delivery.status != WebhookStatus.PENDING:
                logger.warning(f"Delivery {delivery_id} is not pending: {delivery.status}")
                return False
            
            # Prepare webhook payload
            payload = self._prepare_webhook_payload(delivery)
            
            # Generate signature
            signature = self._generate_signature(payload, delivery.webhook.secret)
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'X-Gamification-Signature': signature,
                'X-Gamification-Event': delivery.event.event_type,
                'X-Gamification-Delivery': str(delivery.id),
                'User-Agent': 'Gamification-Webhooks/1.0',
            }
            
            # Add custom headers
            headers.update(delivery.webhook.headers)
            
            # Send webhook
            success = self._send_webhook(
                delivery.webhook.url,
                payload,
                headers,
                delivery
            )
            
            return success
            
        except WebhookDelivery.DoesNotExist:
            logger.error(f"Webhook delivery {delivery_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error processing webhook delivery {delivery_id}: {e}")
            return False
    
    def _prepare_webhook_payload(self, delivery: WebhookDelivery) -> Dict[str, Any]:
        """Prepare webhook payload."""
        payload = {
            'id': str(delivery.event.id),
            'event': delivery.event.event_type,
            'created_at': delivery.event.created_at.isoformat(),
            'data': delivery.event.data,
            'metadata': delivery.event.metadata or {}
        }
        
        if delivery.event.user_id:
            payload['user_id'] = delivery.event.user_id
        
        return payload
    
    def _generate_signature(self, payload: Dict[str, Any], secret: str) -> str:
        """Generate HMAC signature for webhook payload."""
        payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"
    
    def _send_webhook(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        delivery: WebhookDelivery
    ) -> bool:
        """Send webhook to endpoint."""
        import requests
        
        try:
            # Update delivery status
            delivery.status = WebhookStatus.DELIVERING
            delivery.attempts += 1
            delivery.delivered_at = timezone.now()
            delivery.save()
            
            # Send request
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            
            # Check response
            if response.status_code in [200, 201, 202, 204]:
                delivery.status = WebhookStatus.SUCCESS
                delivery.response_status = response.status_code
                delivery.response_body = response.text[:1000]  # Limit response size
                delivery.save()
                
                logger.info(f"Webhook delivery {delivery.id} successful: {response.status_code}")
                return True
            else:
                delivery.status = WebhookStatus.FAILED
                delivery.response_status = response.status_code
                delivery.response_body = response.text[:1000]
                delivery.save()
                
                # Schedule retry if applicable
                if delivery.attempts < self.max_retries:
                    delivery.status = WebhookStatus.RETRY
                    delivery.scheduled_at = timezone.now() + timedelta(seconds=self.retry_delay)
                    delivery.save()
                    
                    # Schedule retry
                    self._process_webhook_delivery.apply_async(
                        args=[delivery.id],
                        eta=delivery.scheduled_at
                    )
                
                logger.warning(f"Webhook delivery {delivery.id} failed: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            delivery.status = WebhookStatus.FAILED
            delivery.response_body = str(e)[:1000]
            delivery.save()
            
            # Schedule retry if applicable
            if delivery.attempts < self.max_retries:
                delivery.status = WebhookStatus.RETRY
                delivery.scheduled_at = timezone.now() + timedelta(seconds=self.retry_delay)
                delivery.save()
                
                # Schedule retry
                self._process_webhook_delivery.apply_async(
                    args=[delivery.id],
                    eta=delivery.scheduled_at
                )
            
            logger.error(f"Webhook delivery {delivery.id} error: {e}")
            return False
    
    def _generate_secret(self) -> str:
        """Generate a random webhook secret."""
        import secrets
        return secrets.token_urlsafe(32)
    
    def verify_webhook_signature(
        self,
        payload: Dict[str, Any],
        signature: str,
        secret: str
    ) -> bool:
        """
        Verify webhook signature.
        
        Args:
            payload: Webhook payload
            signature: Received signature
            secret: Webhook secret
            
        Returns:
            bool: True if signature is valid
        """
        try:
            expected_signature = self._generate_signature(payload, secret)
            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False
    
    def get_webhook_stats(self, webhook_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get webhook statistics.
        
        Args:
            webhook_id: Optional webhook ID to filter by
            
        Returns:
            Dict[str, Any]: Webhook statistics
        """
        try:
            queryset = WebhookDelivery.objects.all()
            
            if webhook_id:
                queryset = queryset.filter(webhook_id=webhook_id)
            
            stats = {
                'total_deliveries': queryset.count(),
                'successful_deliveries': queryset.filter(status=WebhookStatus.SUCCESS).count(),
                'failed_deliveries': queryset.filter(status=WebhookStatus.FAILED).count(),
                'pending_deliveries': queryset.filter(status=WebhookStatus.PENDING).count(),
                'retry_deliveries': queryset.filter(status=WebhookStatus.RETRY).count(),
                'delivering_deliveries': queryset.filter(status=WebhookStatus.DELIVERING).count(),
            }
            
            # Calculate success rate
            if stats['total_deliveries'] > 0:
                stats['success_rate'] = (stats['successful_deliveries'] / stats['total_deliveries']) * 100
            else:
                stats['success_rate'] = 0
            
            # Get recent deliveries
            recent_deliveries = queryset.order_by('-created_at')[:10]
            stats['recent_deliveries'] = [
                {
                    'id': str(delivery.id),
                    'status': delivery.status,
                    'event_type': delivery.event.event_type,
                    'created_at': delivery.created_at.isoformat(),
                    'attempts': delivery.attempts,
                    'response_status': delivery.response_status,
                }
                for delivery in recent_deliveries
            ]
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting webhook stats: {e}")
            return {}
    
    def retry_failed_delivery(self, delivery_id: str) -> bool:
        """
        Retry a failed webhook delivery.
        
        Args:
            delivery_id: Delivery ID
            
        Returns:
            bool: True if retry scheduled successfully
        """
        try:
            delivery = WebhookDelivery.objects.get(id=delivery_id)
            
            if delivery.status not in [WebhookStatus.FAILED]:
                logger.warning(f"Delivery {delivery_id} is not in failed status: {delivery.status}")
                return False
            
            # Reset for retry
            delivery.status = WebhookStatus.PENDING
            delivery.scheduled_at = timezone.now()
            delivery.response_status = None
            delivery.response_body = None
            delivery.save()
            
            # Process retry
            self._process_webhook_delivery.delay(delivery.id)
            
            logger.info(f"Scheduled retry for webhook delivery {delivery_id}")
            return True
            
        except WebhookDelivery.DoesNotExist:
            logger.error(f"Webhook delivery {delivery_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error retrying webhook delivery {delivery_id}: {e}")
            return False


# Signal handlers for automatic webhook triggering
def _handle_badge_earned(sender, **kwargs):
    """Handle badge earned signal."""
    try:
        manager = WebhookManager()
        manager.trigger_webhook(
            event_type=WebhookEventType.BADGE_EARNED,
            data={
                'badge_id': str(kwargs.get('badge_id')),
                'user_badge_id': str(kwargs.get('user_badge_id')),
                'points_bonus': kwargs.get('points_bonus', 0),
            },
            user_id=kwargs.get('user_id'),
            metadata=kwargs.get('metadata', {})
        )
    except Exception as e:
        logger.error(f"Error handling badge earned webhook: {e}")


def _handle_daily_challenge_completed(sender, **kwargs):
    """Handle daily challenge completed signal."""
    try:
        manager = WebhookManager()
        manager.trigger_webhook(
            event_type=WebhookEventType.DAILY_CHALLENGE_COMPLETED,
            data={
                'challenge_id': str(kwargs.get('challenge_id')),
                'user_challenge_id': str(kwargs.get('user_challenge_id')),
                'bonus_points': kwargs.get('bonus_points', 0),
                'completed_at': kwargs.get('completed_at'),
            },
            user_id=kwargs.get('user_id'),
            metadata=kwargs.get('metadata', {})
        )
    except Exception as e:
        logger.error(f"Error handling daily challenge completed webhook: {e}")


def _handle_streak_updated(sender, **kwargs):
    """Handle streak updated signal."""
    try:
        manager = WebhookManager()
        manager.trigger_webhook(
            event_type=WebhookEventType.STREAK_UPDATED,
            data={
                'streak_days': kwargs.get('streak_days'),
                'was_extended': kwargs.get('was_extended', False),
                'days_added': kwargs.get('days_added', 0),
            },
            user_id=kwargs.get('user_id'),
            metadata=kwargs.get('metadata', {})
        )
    except Exception as e:
        logger.error(f"Error handling streak updated webhook: {e}")


def _handle_user_leveled_up(sender, **kwargs):
    """Handle user leveled up signal."""
    try:
        manager = WebhookManager()
        manager.trigger_webhook(
            event_type=WebhookEventType.USER_LEVELED_UP,
            data={
                'old_level': kwargs.get('old_level'),
                'new_level': kwargs.get('new_level'),
                'level_config_id': str(kwargs.get('level_config_id')),
            },
            user_id=kwargs.get('user_id'),
            metadata=kwargs.get('metadata', {})
        )
    except Exception as e:
        logger.error(f"Error handling user leveled up webhook: {e}")


def _handle_achievement_awarded(sender, **kwargs):
    """Handle achievement awarded signal."""
    try:
        manager = WebhookManager()
        manager.trigger_webhook(
            event_type=WebhookEventType.ACHIEVEMENT_AWARDED,
            data={
                'achievement_id': str(kwargs.get('achievement_id')),
                'points_awarded': kwargs.get('points_awarded', 0),
                'rank': kwargs.get('rank'),
            },
            user_id=kwargs.get('user_id'),
            metadata=kwargs.get('metadata', {})
        )
    except Exception as e:
        logger.error(f"Error handling achievement awarded webhook: {e}")


# Connect signal handlers
badge_earned.connect(_handle_badge_earned)
daily_challenge_completed.connect(_handle_daily_challenge_completed)
streak_updated.connect(_handle_streak_updated)
user_leveled_up.connect(_handle_user_leveled_up)
achievement_awarded.connect(_handle_achievement_awarded)


# Celery task for webhook processing
from celery import shared_task

@shared_task(bind=True, max_retries=3)
def _process_webhook_delivery(self, delivery_id: str):
    """Celery task for processing webhook deliveries."""
    try:
        manager = WebhookManager()
        success = manager._process_webhook_delivery(delivery_id)
        
        if not success:
            # Retry with exponential backoff
            countdown = 2 ** self.request.retries
            raise self.retry(countdown=countdown)
        
        return success
        
    except Exception as e:
        logger.error(f"Webhook delivery task failed: {e}")
        raise
