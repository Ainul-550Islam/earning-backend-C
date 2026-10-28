# api/cms/consumers_new/RealTimeOfferConsumer.py
"""
WebSocket Consumers for Real-time Offer Updates
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from asgiref.sync import sync_to_async

from ..models_new.realtime_offers import RealTimeOfferUpdate, UserOfferSubscription
from ..services_new.RealTimeOfferService import RealTimeOfferService, RealTimeOfferWebSocketService

logger = logging.getLogger(__name__)


class RealTimeOfferConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time offer updates
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        user = self.scope["user"]
        
        if not user.is_authenticated:
            await self.close()
            return
        
        self.user_id = user.id
        self.room_group_name = f'user_{self.user_id}_offers'
        
        # Initialize WebSocket service
        self.websocket_service = RealTimeOfferWebSocketService()
        
        # Connect user to their personal group
        await self.websocket_service.connect_user(self.user_id, self.channel_name)
        
        await self.accept()
        
        logger.info(f"User {self.user_id} connected to real-time offers")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, 'websocket_service'):
            await self.websocket_service.disconnect_user(self.user_id, self.channel_name)
        
        logger.info(f"User {self.user_id} disconnected from real-time offers")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'mark_read':
                await self.handle_mark_read(data)
            elif message_type == 'get_updates':
                await self.handle_get_updates()
            elif message_type == 'update_preferences':
                await self.handle_update_preferences(data)
            else:
                await self.send_json({
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}'
                })
                
        except json.JSONDecodeError:
            await self.send_json({
                'type': 'error',
                'message': 'Invalid JSON format'
            })
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            await self.send_json({
                'type': 'error',
                'message': 'Internal server error'
            })
    
    async def handle_mark_read(self, data):
        """Handle mark as read request"""
        update_ids = data.get('update_ids', [])
        
        # This would require a read tracking model
        # For now, just acknowledge
        await self.send_json({
            'type': 'marked_read',
            'count': len(update_ids)
        })
    
    async def handle_get_updates(self):
        """Handle get updates request"""
        user = await sync_to_async(self.scope["user"].__class__.objects.get)(id=self.user_id)
        updates = await sync_to_async(RealTimeOfferService.get_user_updates)(user, limit=20)
        
        await self.send_json({
            'type': 'updates',
            'data': updates
        })
    
    async def handle_update_preferences(self, data):
        """Handle preference update request"""
        try:
            user = await sync_to_async(self.scope["user"].__class__.objects.get)(id=self.user_id)
            subscription = await sync_to_async(UserOfferSubscription.objects.get_or_create)(user=user)[0]
            
            # Update preferences
            for field, value in data.items():
                if hasattr(subscription, field):
                    setattr(subscription, field, value)
            
            await sync_to_async(subscription.save)()
            
            await self.send_json({
                'type': 'preferences_updated',
                'message': 'Preferences updated successfully'
            })
            
        except Exception as e:
            logger.error(f"Error updating preferences: {e}")
            await self.send_json({
                'type': 'error',
                'message': 'Failed to update preferences'
            })
    
    async def offer_update(self, event):
        """Handle offer update event"""
        await self.send_json({
            'type': 'offer_update',
            'data': event['data']
        })
    
    async def initial_updates(self, event):
        """Handle initial updates event"""
        await self.send_json({
            'type': 'initial_updates',
            'data': event['data']
        })
    
    async def send_json(self, data):
        """Send JSON response"""
        await self.send(text_data=json.dumps(data))


class AdminRealTimeOfferConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for admin real-time offer monitoring
    """
    
    async def connect(self):
        """Handle WebSocket connection for admin"""
        user = self.scope["user"]
        
        if not user.is_authenticated or not user.is_staff:
            await self.close()
            return
        
        self.user_id = user.id
        self.room_group_name = f'admin_offers'
        
        # Join admin group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        logger.info(f"Admin user {self.user_id} connected to admin offers monitoring")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        logger.info(f"Admin user {self.user_id} disconnected from admin offers monitoring")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'get_statistics':
                await self.handle_get_statistics()
            elif message_type == 'broadcast_update':
                await self.handle_broadcast_update(data)
            else:
                await self.send_json({
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}'
                })
                
        except json.JSONDecodeError:
            await self.send_json({
                'type': 'error',
                'message': 'Invalid JSON format'
            })
        except Exception as e:
            logger.error(f"Error handling admin WebSocket message: {e}")
            await self.send_json({
                'type': 'error',
                'message': 'Internal server error'
            })
    
    async def handle_get_statistics(self):
        """Handle get statistics request"""
        try:
            from ..services_new.RealTimeOfferService import RealTimeOfferAnalyticsService
            
            stats = await sync_to_async(RealTimeOfferAnalyticsService.get_update_statistics)(days=30)
            
            await self.send_json({
                'type': 'statistics',
                'data': stats
            })
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            await self.send_json({
                'type': 'error',
                'message': 'Failed to get statistics'
            })
    
    async def handle_broadcast_update(self, data):
        """Handle broadcast update request"""
        try:
            update_uuid = data.get('update_uuid')
            if not update_uuid:
                await self.send_json({
                    'type': 'error',
                    'message': 'update_uuid required'
                })
                return
            
            # Trigger broadcast
            await self.channel_layer.group_send(
                'offer_updates',
                {
                    'type': 'broadcast_offer_update',
                    'update_uuid': update_uuid
                }
            )
            
            await self.send_json({
                'type': 'broadcast_queued',
                'update_uuid': update_uuid
            })
            
        except Exception as e:
            logger.error(f"Error broadcasting update: {e}")
            await self.send_json({
                'type': 'error',
                'message': 'Failed to broadcast update'
            })
    
    async def offer_update_created(self, event):
        """Handle offer update created event"""
        await self.send_json({
            'type': 'offer_update_created',
            'data': event
        })
    
    async def send_json(self, data):
        """Send JSON response"""
        await self.send(text_data=json.dumps(data))


class ABTestingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for A/B testing real-time updates
    """
    
    async def connect(self):
        """Handle WebSocket connection for A/B testing"""
        user = self.scope["user"]
        
        if not user.is_authenticated:
            await self.close()
            return
        
        self.user_id = user.id
        self.room_group_name = f'user_{self.user_id}_ab_testing'
        
        # Join user's A/B testing group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        logger.info(f"User {self.user_id} connected to A/B testing updates")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        logger.info(f"User {self.user_id} disconnected from A/B testing updates")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'get_user_variants':
                await self.handle_get_user_variants()
            elif message_type == 'track_engagement':
                await self.handle_track_engagement(data)
            else:
                await self.send_json({
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}'
                })
                
        except json.JSONDecodeError:
            await self.send_json({
                'type': 'error',
                'message': 'Invalid JSON format'
            })
        except Exception as e:
            logger.error(f"Error handling A/B testing WebSocket message: {e}")
            await self.send_json({
                'type': 'error',
                'message': 'Internal server error'
            })
    
    async def handle_get_user_variants(self):
        """Handle get user variants request"""
        try:
            from ..services_new.ABTestingService import ABTestingManager
            
            user = await sync_to_async(self.scope["user"].__class__.objects.get)(id=self.user_id)
            running_tests = await sync_to_async(ABTestingManager().get_running_tests)()
            
            variants = []
            for test in running_tests:
                variant = await sync_to_async(ABTestingManager().get_user_variant)(str(test.uuid), user)
                if variant:
                    variants.append({
                        'test_uuid': str(test.uuid),
                        'test_name': test.name,
                        'variant_uuid': str(variant.uuid),
                        'variant_name': variant.name,
                        'is_control': variant.is_control
                    })
            
            await self.send_json({
                'type': 'user_variants',
                'data': variants
            })
            
        except Exception as e:
            logger.error(f"Error getting user variants: {e}")
            await self.send_json({
                'type': 'error',
                'message': 'Failed to get user variants'
            })
    
    async def handle_track_engagement(self, data):
        """Handle engagement tracking"""
        try:
            from ..services_new.ABTestingService import ABTestingManager
            
            test_uuid = data.get('test_uuid')
            engagement_type = data.get('type')
            value = data.get('value', 1)
            
            if not test_uuid or not engagement_type:
                await self.send_json({
                    'type': 'error',
                    'message': 'test_uuid and type required'
                })
                return
            
            user = await sync_to_async(self.scope["user"].__class__.objects.get)(id=self.user_id)
            success = await sync_to_async(ABTestingManager().track_engagement)(
                test_uuid, user, engagement_type, value
            )
            
            if success:
                await self.send_json({
                    'type': 'engagement_tracked',
                    'test_uuid': test_uuid,
                    'type': engagement_type,
                    'value': value
                })
            else:
                await self.send_json({
                    'type': 'error',
                    'message': 'Failed to track engagement'
                })
                
        except Exception as e:
            logger.error(f"Error tracking engagement: {e}")
            await self.send_json({
                'type': 'error',
                'message': 'Failed to track engagement'
            })
    
    async def test_update(self, event):
        """Handle test update event"""
        await self.send_json({
            'type': 'test_update',
            'data': event['data']
        })
    
    async def send_json(self, data):
        """Send JSON response"""
        await self.send(text_data=json.dumps(data))
