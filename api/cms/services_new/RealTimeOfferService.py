# api/cms/services_new/RealTimeOfferService.py
"""
Service layer for Real-time Offer Updates
Handles WebSocket connections, notifications, and update processing
"""
import json
import logging
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync, sync_to_async

from ..models_new.realtime_offers import (
    RealTimeOfferUpdate, UserOfferSubscription, OfferUpdateQueue
)

logger = logging.getLogger(__name__)
User = get_user_model()


class RealTimeOfferWebSocketService:
    """
    WebSocket service for real-time offer updates
    """
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
    
    async def connect_user(self, user_id: int, channel_name: str):
        """Connect user to real-time updates"""
        # Add user to their personal group
        await self.channel_layer.group_add(
            f'user_{user_id}_offers',
            channel_name
        )
        
        # Send initial updates
        await self.send_initial_updates(user_id, channel_name)
        
        logger.info(f"User {user_id} connected to real-time offers")
    
    async def disconnect_user(self, user_id: int, channel_name: str):
        """Disconnect user from real-time updates"""
        await self.channel_layer.group_discard(
            f'user_{user_id}_offers',
            channel_name
        )
        
        logger.info(f"User {user_id} disconnected from real-time offers")
    
    async def send_initial_updates(self, user_id: int, channel_name: str):
        """Send recent updates to newly connected user"""
        from ..models_new.realtime_offers import RealTimeOfferService
        
        user = await sync_to_async(User.objects.get)(id=user_id)
        updates = await sync_to_async(RealTimeOfferService.get_user_updates)(user, limit=20)
        
        if updates:
            await self.channel_layer.send(
                channel_name,
                {
                    'type': 'initial_updates',
                    'data': updates
                }
            )
    
    async def broadcast_offer_update(self, update_uuid: str):
        """Broadcast offer update to all relevant users"""
        from ..models_new.realtime_offers import RealTimeOfferUpdate
        
        try:
            update = await sync_to_async(RealTimeOfferUpdate.objects.get)(uuid=update_uuid)
            await sync_to_async(RealTimeOfferService.broadcast_update)(update)
        except RealTimeOfferUpdate.DoesNotExist:
            logger.error(f"Offer update {update_uuid} not found")
    
    async def process_update_queue(self):
        """Process queued updates in background"""
        from ..models_new.realtime_offers import RealTimeOfferService
        
        while True:
            try:
                # Get unprocessed queue items
                queue_items = await sync_to_async(OfferUpdateQueue.objects.filter)(
                    status='pending'
                ).order_by('created_at')[:10]
                
                for item in queue_items:
                    try:
                        # Process batch data
                        await self._process_batch_update(item.batch_data)
                        
                        # Mark as processed
                        item.status = 'processed'
                        item.processed_at = timezone.now()
                        await sync_to_async(item.save)()
                        
                    except Exception as e:
                        logger.error(f"Error processing queue item {item.uuid}: {e}")
                        item.status = 'failed'
                        item.error_message = str(e)
                        await sync_to_async(item.save)()
                
                # Wait before next batch
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Error in update queue processing: {e}")
                await asyncio.sleep(30)
    
    async def _process_batch_update(self, batch_data: dict):
        """Process a batch of offer updates"""
        update_type = batch_data.get('type')
        offers = batch_data.get('offers', [])
        
        if update_type == 'bulk_update':
            for offer_data in offers:
                await self._create_and_broadcast_update(offer_data)
        elif update_type == 'price_change':
            await self._handle_price_changes(offers)
    
    async def _create_and_broadcast_update(self, offer_data: dict):
        """Create update and broadcast to users"""
        from ..models_new.realtime_offers import RealTimeOfferService
        
        update = await sync_to_async(RealTimeOfferService.create_offer_update)(
            offer_id=offer_data['offer_id'],
            update_type=offer_data['update_type'],
            old_data=offer_data.get('old_data'),
            new_data=offer_data.get('new_data'),
            targeting=offer_data.get('targeting'),
            priority=offer_data.get('priority', 0)
        )
        
        await self.broadcast_offer_update(str(update.uuid))
    
    async def _handle_price_changes(self, offers: list):
        """Handle bulk price changes"""
        for offer_data in offers:
            await self._create_and_broadcast_update({
                'offer_id': offer_data['offer_id'],
                'update_type': 'payout_changed',
                'old_data': {'payout': offer_data.get('old_payout')},
                'new_data': {'payout': offer_data.get('new_payout')},
                'priority': 5  # High priority for price changes
            })


class RealTimeOfferNotificationService:
    """
    Service for sending real-time notifications
    """
    
    @staticmethod
    async def send_push_notification(user_id: int, title: str, message: str, data: dict = None):
        """Send push notification to user"""
        # This would integrate with your push notification service
        channel_layer = get_channel_layer()
        
        await channel_layer.group_send(
            f'user_{user_id}_notifications',
            {
                'type': 'push_notification',
                'data': {
                    'title': title,
                    'message': message,
                    'data': data or {},
                    'timestamp': timezone.now().isoformat()
                }
            }
        )
    
    @staticmethod
    async def send_email_notification(user_id: int, subject: str, message: str):
        """Send email notification (for high-priority updates)"""
        from django.core.mail import send_mail
        from django.conf import settings
        
        try:
            user = await sync_to_async(User.objects.get)(id=user_id)
            
            await sync_to_async(send_mail)(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False
            )
        except Exception as e:
            logger.error(f"Failed to send email notification to user {user_id}: {e}")
    
    @staticmethod
    async def notify_offer_update(user_id: int, update_data: dict):
        """Notify user about offer update"""
        update_type = update_data.get('update_type')
        offer_id = update_data.get('offer_id')
        
        # Generate notification content
        notifications = {
            'new_offer': {
                'title': '🎉 New Offer Available!',
                'message': f'New offer {offer_id} is now available. Check it out now!',
                'priority': 'normal'
            },
            'offer_updated': {
                'title': '📝 Offer Updated',
                'message': f'Offer {offer_id} has been updated with new details.',
                'priority': 'normal'
            },
            'offer_expired': {
                'title': '⏰ Offer Expired',
                'message': f'Offer {offer_id} has expired and is no longer available.',
                'priority': 'low'
            },
            'payout_changed': {
                'title': '💰 Payout Changed!',
                'message': f'Offer {offer_id} payout has been updated. Check new rates!',
                'priority': 'high'
            }
        }
        
        notification = notifications.get(update_type, {
            'title': 'Offer Update',
            'message': f'Offer {offer_id} has been updated.',
            'priority': 'normal'
        })
        
        # Send push notification
        await RealTimeOfferNotificationService.send_push_notification(
            user_id=user_id,
            title=notification['title'],
            message=notification['message'],
            data=update_data
        )
        
        # Send email for high-priority updates
        if notification['priority'] == 'high':
            await RealTimeOfferNotificationService.send_email_notification(
                user_id=user_id,
                subject=notification['title'],
                message=notification['message']
            )


class RealTimeOfferAnalyticsService:
    """
    Analytics service for real-time offer updates
    """
    
    @staticmethod
    def get_update_statistics(days: int = 30) -> dict:
        """Get statistics about offer updates"""
        from django.db.models import Count, Avg
        from ..models_new.realtime_offers import RealTimeOfferUpdate
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        stats = RealTimeOfferUpdate.objects.filter(
            created_at__gte=cutoff_date
        ).aggregate(
            total_updates=Count('id'),
            avg_priority=Avg('priority'),
            by_type=Count('update_type')
        )
        
        # Get breakdown by type
        type_breakdown = {}
        for update_type in RealTimeOfferUpdate.UPDATE_TYPES:
            type_code = update_type[0]
            count = RealTimeOfferUpdate.objects.filter(
                update_type=type_code,
                created_at__gte=cutoff_date
            ).count()
            type_breakdown[update_type[1]] = count
        
        return {
            'period_days': days,
            'total_updates': stats['total_updates'] or 0,
            'avg_priority': float(stats['avg_priority'] or 0),
            'type_breakdown': type_breakdown,
            'updates_per_day': round((stats['total_updates'] or 0) / days, 2)
        }
    
    @staticmethod
    def get_user_engagement_stats(user_id: int, days: int = 30) -> dict:
        """Get engagement statistics for a user"""
        from ..models_new.realtime_offers import UserOfferSubscription
        
        try:
            subscription = UserOfferSubscription.objects.get(user_id=user_id)
        except UserOfferSubscription.DoesNotExist:
            return {'error': 'User not subscribed'}
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get engagement metrics
        # This would require additional tracking models
        
        return {
            'user_id': user_id,
            'period_days': days,
            'subscription_preferences': {
                'new_offers': subscription.subscribe_new_offers,
                'updated_offers': subscription.subscribe_updated_offers,
                'expired_offers': subscription.subscribe_expired_offers,
                'payout_changes': subscription.subscribe_payout_changes,
            },
            'notification_settings': {
                'sound': subscription.notification_sound,
                'desktop': subscription.notification_desktop,
                'email': subscription.notification_email,
            }
        }
    
    @staticmethod
    def get_performance_metrics() -> dict:
        """Get performance metrics for the real-time system"""
        from django.core.cache import cache
        
        # Get cache metrics
        cache_info = cache._client.info() if hasattr(cache._client, 'info') else {}
        
        # Get WebSocket connection count
        active_connections = cache.get('active_websocket_connections', 0)
        
        # Get queue size
        queue_size = OfferUpdateQueue.objects.filter(status='pending').count()
        
        return {
            'active_websocket_connections': active_connections,
            'pending_queue_items': queue_size,
            'cache_hit_rate': cache_info.get('keyspace_hits', 0),
            'cache_memory_usage': cache_info.get('used_memory', 0),
            'last_cleanup': cache.get('last_cleanup_time'),
            'system_uptime': cache.get('system_start_time', timezone.now())
        }


# Convenience alias used by services_new/__init__.py and tests
RealTimeOfferService = RealTimeOfferWebSocketService
