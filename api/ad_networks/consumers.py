"""
api/ad_networks/consumers.py
WebSocket consumers for real-time ad networks updates
SaaS-ready with tenant support
"""

import json
import logging
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from channels.auth import login
from channels.layers import get_channel_layer
from asgiref.sync import sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction

from api.ad_networks.models import (
    Offer, UserOfferEngagement, OfferConversion, 
    OfferReward, AdNetwork, NetworkHealthCheck
)
from api.ad_networks.choices import (
    OfferStatus, EngagementStatus, ConversionStatus,
    RewardStatus, NetworkStatus
)

logger = logging.getLogger(__name__)


class OfferUpdatesConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time offer updates
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope["user"]
        self.tenant_id = getattr(self.scope, 'tenant_id', 'default')
        
        # Check if user is authenticated
        if isinstance(self.user, AnonymousUser):
            await self.close(code=4001)
            return
        
        # Create unique room name for user
        self.room_group_name = f"offers_{self.tenant_id}_{self.user.id}"
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial data
        await self.send_initial_data()
        
        logger.info(f"User {self.user.id} connected to offers updates")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        logger.info(f"User {self.user.id} disconnected from offers updates")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'subscribe_offers':
                await self.handle_subscribe_offers(data)
            elif message_type == 'subscribe_network':
                await self.handle_subscribe_network(data)
            elif message_type == 'get_offer_details':
                await self.handle_get_offer_details(data)
            elif message_type == 'mark_offer_viewed':
                await self.handle_mark_offer_viewed(data)
            else:
                await self.send_error(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            await self.send_error("Internal server error")
    
    async def send_initial_data(self):
        """Send initial data to connected client"""
        try:
            # Get user's recent offers
            recent_offers = await self.get_recent_offers()
            
            # Get user's stats
            user_stats = await self.get_user_stats()
            
            initial_data = {
                'type': 'initial_data',
                'recent_offers': recent_offers,
                'user_stats': user_stats,
                'timestamp': timezone.now().isoformat()
            }
            
            await self.send(text_data=json.dumps(initial_data))
            
        except Exception as e:
            logger.error(f"Error sending initial data: {str(e)}")
    
    async def handle_subscribe_offers(self, data):
        """Handle subscription to specific offers"""
        offer_ids = data.get('offer_ids', [])
        
        if not isinstance(offer_ids, list):
            await self.send_error("offer_ids must be a list")
            return
        
        # Validate offers exist and belong to user's tenant
        valid_offers = await self.validate_offers(offer_ids)
        
        if len(valid_offers) != len(offer_ids):
            await self.send_error("Some offers are invalid")
            return
        
        # Subscribe to offer updates
        for offer_id in valid_offers:
            offer_room = f"offer_{self.tenant_id}_{offer_id}"
            await self.channel_layer.group_add(
                offer_room,
                self.channel_name
            )
        
        await self.send_success(f"Subscribed to {len(valid_offers)} offers")
    
    async def handle_subscribe_network(self, data):
        """Handle subscription to network updates"""
        network_id = data.get('network_id')
        
        if not network_id:
            await self.send_error("network_id is required")
            return
        
        # Validate network exists and belongs to tenant
        network = await self.get_network(network_id)
        if not network:
            await self.send_error("Network not found")
            return
        
        # Subscribe to network updates
        network_room = f"network_{self.tenant_id}_{network_id}"
        await self.channel_layer.group_add(
            network_room,
            self.channel_name
        )
        
        await self.send_success(f"Subscribed to network {network_id}")
    
    async def handle_get_offer_details(self, data):
        """Handle request for offer details"""
        offer_id = data.get('offer_id')
        
        if not offer_id:
            await self.send_error("offer_id is required")
            return
        
        # Get offer details
        offer = await self.get_offer_details(offer_id)
        if not offer:
            await self.send_error("Offer not found")
            return
        
        response_data = {
            'type': 'offer_details',
            'offer': offer
        }
        
        await self.send(text_data=json.dumps(response_data))
    
    async def handle_mark_offer_viewed(self, data):
        """Handle marking offer as viewed"""
        offer_id = data.get('offer_id')
        
        if not offer_id:
            await self.send_error("offer_id is required")
            return
        
        # Mark offer as viewed
        success = await self.mark_offer_viewed(offer_id)
        
        if success:
            await self.send_success("Offer marked as viewed")
        else:
            await self.send_error("Failed to mark offer as viewed")
    
    @database_sync_to_async
    def get_recent_offers(self):
        """Get recent offers for user"""
        from api.ad_networks.services.OfferRecommendService import OfferRecommendService
        
        try:
            service = OfferRecommendService(tenant_id=self.tenant_id)
            result = service.get_personalized_recommendations(self.user.id, limit=10)
            
            if result['success']:
                return result['recommendations']
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error getting recent offers: {str(e)}")
            return []
    
    @database_sync_to_async
    def get_user_stats(self):
        """Get user statistics"""
        try:
            # Get user's offer stats
            from django.db.models import Count, Sum, Q
            from api.ad_networks.models import UserOfferEngagement, OfferConversion, OfferReward
            
            total_engagements = UserOfferEngagement.objects.filter(
                user=self.user,
                tenant_id=self.tenant_id
            ).count()
            
            completed_engagements = UserOfferEngagement.objects.filter(
                user=self.user,
                status__in=[EngagementStatus.COMPLETED, EngagementStatus.APPROVED],
                tenant_id=self.tenant_id
            ).count()
            
            total_conversions = OfferConversion.objects.filter(
                engagement__user=self.user,
                tenant_id=self.tenant_id
            ).count()
            
            approved_conversions = OfferConversion.objects.filter(
                engagement__user=self.user,
                conversion_status=ConversionStatus.APPROVED,
                tenant_id=self.tenant_id
            ).count()
            
            total_rewards = OfferReward.objects.filter(
                user=self.user,
                status=RewardStatus.APPROVED,
                tenant_id=self.tenant_id
            ).aggregate(
                total=Sum('amount')
            )['total'] or 0
            
            return {
                'total_engagements': total_engagements,
                'completed_engagements': completed_engagements,
                'total_conversions': total_conversions,
                'approved_conversions': approved_conversions,
                'total_rewards': float(total_rewards),
                'completion_rate': (completed_engagements / total_engagements * 100) if total_engagements > 0 else 0,
                'conversion_rate': (approved_conversions / total_conversions * 100) if total_conversions > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting user stats: {str(e)}")
            return {}
    
    @database_sync_to_async
    def validate_offers(self, offer_ids):
        """Validate offers exist and belong to tenant"""
        try:
            offers = Offer.objects.filter(
                id__in=offer_ids,
                tenant_id=self.tenant_id,
                status=OfferStatus.ACTIVE
            ).values_list('id', flat=True)
            
            return list(offers)
            
        except Exception as e:
            logger.error(f"Error validating offers: {str(e)}")
            return []
    
    @database_sync_to_async
    def get_network(self, network_id):
        """Get network by ID"""
        try:
            return AdNetwork.objects.get(
                id=network_id,
                tenant_id=self.tenant_id
            )
        except AdNetwork.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting network: {str(e)}")
            return None
    
    @database_sync_to_async
    def get_offer_details(self, offer_id):
        """Get offer details"""
        try:
            offer = Offer.objects.get(
                id=offer_id,
                tenant_id=self.tenant_id
            )
            
            return {
                'id': offer.id,
                'title': offer.title,
                'description': offer.description,
                'reward_amount': float(offer.reward_amount),
                'currency': offer.reward_currency,
                'status': offer.status,
                'countries': offer.countries,
                'platforms': offer.platforms,
                'device_type': offer.device_type,
                'difficulty': offer.difficulty,
                'estimated_time': offer.estimated_time,
                'is_featured': offer.is_featured,
                'is_hot': offer.is_hot,
                'is_new': offer.is_new,
                'created_at': offer.created_at.isoformat(),
                'updated_at': offer.updated_at.isoformat() if offer.updated_at else None
            }
            
        except Offer.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting offer details: {str(e)}")
            return None
    
    @database_sync_to_async
    def mark_offer_viewed(self, offer_id):
        """Mark offer as viewed by user"""
        try:
            # Check if user has engagement for this offer
            engagement = UserOfferEngagement.objects.filter(
                user=self.user,
                offer_id=offer_id,
                tenant_id=self.tenant_id
            ).first()
            
            if engagement:
                # Update last viewed time
                engagement.last_viewed_at = timezone.now()
                engagement.view_count += 1
                engagement.save(update_fields=['last_viewed_at', 'view_count'])
                return True
            else:
                # Create new engagement record
                UserOfferEngagement.objects.create(
                    user=self.user,
                    offer_id=offer_id,
                    status=EngagementStatus.VIEWED,
                    last_viewed_at=timezone.now(),
                    view_count=1,
                    tenant_id=self.tenant_id
                )
                return True
                
        except Exception as e:
            logger.error(f"Error marking offer as viewed: {str(e)}")
            return False
    
    async def send_success(self, message):
        """Send success message"""
        await self.send(text_data=json.dumps({
            'type': 'success',
            'message': message,
            'timestamp': timezone.now().isoformat()
        }))
    
    async def send_error(self, message):
        """Send error message"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'timestamp': timezone.now().isoformat()
        }))
    
    async def offer_update(self, event):
        """Handle offer update event"""
        if event['tenant_id'] != self.tenant_id:
            return
        
        await self.send(text_data=json.dumps({
            'type': 'offer_update',
            'offer': event['offer'],
            'action': event['action'],
            'timestamp': event['timestamp']
        }))
    
    async def network_update(self, event):
        """Handle network update event"""
        if event['tenant_id'] != self.tenant_id:
            return
        
        await self.send(text_data=json.dumps({
            'type': 'network_update',
            'network': event['network'],
            'action': event['action'],
            'timestamp': event['timestamp']
        }))
    
    async def conversion_update(self, event):
        """Handle conversion update event"""
        if event['user_id'] != self.user.id:
            return
        
        await self.send(text_data=json.dumps({
            'type': 'conversion_update',
            'conversion': event['conversion'],
            'action': event['action'],
            'timestamp': event['timestamp']
        }))
    
    async def reward_update(self, event):
        """Handle reward update event"""
        if event['user_id'] != self.user.id:
            return
        
        await self.send(text_data=json.dumps({
            'type': 'reward_update',
            'reward': event['reward'],
            'action': event['action'],
            'timestamp': event['timestamp']
        }))


class NetworkHealthConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time network health updates
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope["user"]
        self.tenant_id = getattr(self.scope, 'tenant_id', 'default')
        
        # Check if user is admin
        if not self.user.is_staff:
            await self.close(code=4003)
            return
        
        # Create room name for tenant
        self.room_group_name = f"network_health_{self.tenant_id}"
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial health data
        await self.send_initial_health_data()
        
        logger.info(f"Admin user {self.user.id} connected to network health updates")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        logger.info(f"Admin user {self.user.id} disconnected from network health updates")
    
    async def send_initial_health_data(self):
        """Send initial network health data"""
        try:
            # Get all networks for tenant
            networks = await self.get_tenant_networks()
            
            # Get health status for each network
            health_data = []
            for network in networks:
                health = await self.get_network_health(network['id'])
                health_data.append({
                    'network': network,
                    'health': health
                })
            
            initial_data = {
                'type': 'initial_health_data',
                'networks': health_data,
                'timestamp': timezone.now().isoformat()
            }
            
            await self.send(text_data=json.dumps(initial_data))
            
        except Exception as e:
            logger.error(f"Error sending initial health data: {str(e)}")
    
    @database_sync_to_async
    def get_tenant_networks(self):
        """Get all networks for tenant"""
        try:
            networks = AdNetwork.objects.filter(
                tenant_id=self.tenant_id
            ).values('id', 'name', 'network_type', 'status', 'is_active')
            
            return list(networks)
            
        except Exception as e:
            logger.error(f"Error getting tenant networks: {str(e)}")
            return []
    
    @database_sync_to_async
    def get_network_health(self, network_id):
        """Get network health status"""
        try:
            # Get latest health check
            health_check = NetworkHealthCheck.objects.filter(
                network_id=network_id
            ).order_by('-checked_at').first()
            
            if health_check:
                return {
                    'is_healthy': health_check.is_healthy,
                    'response_time_ms': health_check.response_time_ms,
                    'status_code': health_check.status_code,
                    'error': health_check.error,
                    'checked_at': health_check.checked_at.isoformat()
                }
            else:
                return {
                    'is_healthy': None,
                    'response_time_ms': None,
                    'status_code': None,
                    'error': 'No health checks',
                    'checked_at': None
                }
                
        except Exception as e:
            logger.error(f"Error getting network health: {str(e)}")
            return {
                'is_healthy': None,
                'error': str(e)
            }
    
    async def health_check_update(self, event):
        """Handle health check update event"""
        if event['tenant_id'] != self.tenant_id:
            return
        
        await self.send(text_data=json.dumps({
            'type': 'health_check_update',
            'network_id': event['network_id'],
            'health': event['health'],
            'timestamp': event['timestamp']
        }))


class ConversionUpdatesConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time conversion updates
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope["user"]
        self.tenant_id = getattr(self.scope, 'tenant_id', 'default')
        
        # Check if user is authenticated
        if isinstance(self.user, AnonymousUser):
            await self.close(code=4001)
            return
        
        # Create room name for user conversions
        self.room_group_name = f"conversions_{self.tenant_id}_{self.user.id}"
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial conversion data
        await self.send_initial_conversion_data()
        
        logger.info(f"User {self.user.id} connected to conversion updates")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        logger.info(f"User {self.user.id} disconnected from conversion updates")
    
    async def send_initial_conversion_data(self):
        """Send initial conversion data"""
        try:
            # Get recent conversions
            recent_conversions = await self.get_recent_conversions()
            
            initial_data = {
                'type': 'initial_conversion_data',
                'recent_conversions': recent_conversions,
                'timestamp': timezone.now().isoformat()
            }
            
            await self.send(text_data=json.dumps(initial_data))
            
        except Exception as e:
            logger.error(f"Error sending initial conversion data: {str(e)}")
    
    @database_sync_to_async
    def get_recent_conversions(self):
        """Get recent conversions for user"""
        try:
            from django.db.models import Q
            from api.ad_networks.models import OfferConversion, UserOfferEngagement
            
            conversions = OfferConversion.objects.filter(
                engagement__user=self.user,
                tenant_id=self.tenant_id
            ).select_related(
                'engagement', 'engagement__offer', 'engagement__offer__ad_network'
            ).order_by('-created_at')[:10]
            
            conversion_data = []
            for conversion in conversions:
                conversion_data.append({
                    'id': conversion.id,
                    'offer_id': conversion.engagement.offer.id,
                    'offer_title': conversion.engagement.offer.title,
                    'network_name': conversion.engagement.offer.ad_network.name,
                    'payout': float(conversion.payout or 0),
                    'status': conversion.conversion_status,
                    'fraud_score': conversion.fraud_score,
                    'created_at': conversion.created_at.isoformat()
                })
            
            return conversion_data
            
        except Exception as e:
            logger.error(f"Error getting recent conversions: {str(e)}")
            return []
    
    async def conversion_update(self, event):
        """Handle conversion update event"""
        if event['user_id'] != self.user.id:
            return
        
        await self.send(text_data=json.dumps({
            'type': 'conversion_update',
            'conversion': event['conversion'],
            'action': event['action'],
            'timestamp': event['timestamp']
        }))


# WebSocket event handlers
async def offer_created_handler(event):
    """Handle offer created event"""
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        f"offers_{event['tenant_id']}",
        {
            'type': 'offer_update',
            'offer': event['offer'],
            'action': 'created',
            'timestamp': event['timestamp']
        }
    )


async def offer_updated_handler(event):
    """Handle offer updated event"""
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        f"offers_{event['tenant_id']}",
        {
            'type': 'offer_update',
            'offer': event['offer'],
            'action': 'updated',
            'timestamp': event['timestamp']
        }
    )


async def network_health_updated_handler(event):
    """Handle network health updated event"""
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        f"network_health_{event['tenant_id']}",
        {
            'type': 'health_check_update',
            'network_id': event['network_id'],
            'health': event['health'],
            'timestamp': event['timestamp']
        }
    )


async def conversion_created_handler(event):
    """Handle conversion created event"""
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        f"conversions_{event['tenant_id']}_{event['user_id']}",
        {
            'type': 'conversion_update',
            'conversion': event['conversion'],
            'action': 'created',
            'timestamp': event['timestamp']
        }
    )


# Consumer routing configuration
websocket_urlpatterns = [
    re_path(r'ws/ad_networks/offers/(?P<tenant_id>\w+)/$', OfferUpdatesConsumer.as_asgi()),
    re_path(r'ws/ad_networks/health/(?P<tenant_id>\w+)/$', NetworkHealthConsumer.as_asgi()),
    re_path(r'ws/ad_networks/conversions/(?P<tenant_id>\w+)/$', ConversionUpdatesConsumer.as_asgi()),
]
