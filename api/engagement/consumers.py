# engagement/consumers.py
"""
WebSocket consumers for real-time engagement features.
Handles real-time updates for leaderboards, notifications, social feeds, etc.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist

from .services import NotificationService, LeaderboardService, SocialService
from .utils.cache import get_user_online_status, set_user_online_status


class EngagementConsumer(AsyncWebsocketConsumer):
    """
    Main engagement WebSocket consumer.
    Handles multiple engagement features in one connection.
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope["user"]
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Create personal room for this user
        self.room_name = f"engagement_user_{self.user.id}"
        self.room_group_name = f"engagement_{self.room_name}"
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # Set user as online
        await set_user_online_status(self.user.id, True)
        
        await self.accept()
        
        # Send initial data
        await self.send_initial_data()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
        
        # Set user as offline
        await set_user_online_status(self.user.id, False)
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'ping':
                await self.handle_ping()
            elif message_type == 'mark_notification_read':
                await self.handle_mark_notification_read(data)
            elif message_type == 'like_feed_item':
                await self.handle_like_feed_item(data)
            elif message_type == 'comment_feed_item':
                await self.handle_comment_feed_item(data)
            else:
                await self.send_error("Unknown message type")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
        except Exception as exc:
            await self.send_error(str(exc))
    
    async def send_initial_data(self):
        """Send initial data to connected user."""
        try:
            # Get unread notifications count
            unread_count = await self.get_unread_notifications_count()
            
            # Get current leaderboard position
            leaderboard_position = await self.get_leaderboard_position()
            
            # Get online friends
            online_friends = await self.get_online_friends()
            
            await self.send(text_data=json.dumps({
                'type': 'initial_data',
                'unread_notifications': unread_count,
                'leaderboard_position': leaderboard_position,
                'online_friends': online_friends
            }))
            
        except Exception as exc:
            await self.send_error(f"Failed to load initial data: {str(exc)}")
    
    async def handle_ping(self):
        """Handle ping message for connection health check."""
        await self.send(text_data=json.dumps({'type': 'pong'}))
    
    async def handle_mark_notification_read(self, data):
        """Handle marking notification as read."""
        notification_id = data.get('notification_id')
        if notification_id:
            try:
                await self.mark_notification_read(notification_id)
                await self.send(text_data=json.dumps({
                    'type': 'notification_marked_read',
                    'notification_id': notification_id
                }))
            except Exception as exc:
                await self.send_error(f"Failed to mark notification: {str(exc)}")
    
    async def handle_like_feed_item(self, data):
        """Handle feed item like."""
        feed_item_id = data.get('feed_item_id')
        if feed_item_id:
            try:
                result = await self.like_feed_item(feed_item_id)
                await self.send(text_data=json.dumps({
                    'type': 'feed_item_liked',
                    'feed_item_id': feed_item_id,
                    'likes_count': result['likes_count'],
                    'is_liked': result['is_liked']
                }))
            except Exception as exc:
                await self.send_error(f"Failed to like feed item: {str(exc)}")
    
    async def handle_comment_feed_item(self, data):
        """Handle feed item comment."""
        feed_item_id = data.get('feed_item_id')
        comment_text = data.get('comment')
        if feed_item_id and comment_text:
            try:
                comment = await self.comment_feed_item(feed_item_id, comment_text)
                await self.send(text_data=json.dumps({
                    'type': 'feed_item_commented',
                    'comment': comment
                }))
            except Exception as exc:
                await self.send_error(f"Failed to comment on feed item: {str(exc)}")
    
    # ── Database Operations ───────────────────────────────────────────────────
    
    @database_sync_to_async
    def get_unread_notifications_count(self):
        """Get unread notifications count for user."""
        return NotificationService.unread_count(self.user)
    
    @database_sync_to_async
    def get_leaderboard_position(self):
        """Get user's current leaderboard position."""
        try:
            return LeaderboardService.get_user_rank(self.user)
        except:
            return None
    
    @database_sync_to_async
    def get_online_friends(self):
        """Get list of online friends."""
        try:
            friends = self.user.friends.all()
            online_friends = []
            for friend in friends:
                if get_user_online_status(friend.id):
                    online_friends.append({
                        'id': friend.id,
                        'username': friend.username,
                        'avatar': getattr(friend, 'avatar_url', None)
                    })
            return online_friends
        except:
            return []
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark notification as read."""
        return NotificationService.mark_as_read(self.user, notification_id)
    
    @database_sync_to_async
    def like_feed_item(self, feed_item_id):
        """Like a feed item."""
        return SocialService.like_feed_item(self.user, feed_item_id)
    
    @database_sync_to_async
    def comment_feed_item(self, feed_item_id, comment_text):
        """Comment on a feed item."""
        return SocialService.comment_feed_item(self.user, feed_item_id, comment_text)
    
    # ── Message Broadcasting ───────────────────────────────────────────────────
    
    async def engagement_notification(self, event):
        """Handle engagement notification broadcast."""
        await self.send(text_data=json.dumps({
            'type': 'engagement_notification',
            'notification': event['notification']
        }))
    
    async def leaderboard_update(self, event):
        """Handle leaderboard update broadcast."""
        await self.send(text_data=json.dumps({
            'type': 'leaderboard_update',
            'leaderboard': event['leaderboard']
        }))
    
    async def social_feed_update(self, event):
        """Handle social feed update broadcast."""
        await self.send(text_data=json.dumps({
            'type': 'social_feed_update',
            'feed_item': event['feed_item']
        }))
    
    async def friend_online_status(self, event):
        """Handle friend online status change broadcast."""
        await self.send(text_data=json.dumps({
            'type': 'friend_online_status',
            'friend_id': event['friend_id'],
            'online': event['online']
        }))
    
    # ── Utility Methods ───────────────────────────────────────────────────────
    
    async def send_error(self, error_message):
        """Send error message to client."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'error': error_message
        }))


class LeaderboardConsumer(AsyncWebsocketConsumer):
    """
    Dedicated leaderboard WebSocket consumer.
    Provides real-time leaderboard updates.
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope["user"]
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Join leaderboard room
        self.room_group_name = "leaderboard_global"
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial leaderboard data
        await self.send_leaderboard_data()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'get_leaderboard':
                period = data.get('period', 'daily')
                await self.send_leaderboard_data(period)
            else:
                await self.send_error("Unknown message type")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
    
    @database_sync_to_async
    def get_leaderboard_data(self, period='daily'):
        """Get leaderboard data."""
        try:
            return LeaderboardService.get_top_leaderboard(period, limit=50)
        except:
            return []
    
    async def send_leaderboard_data(self, period='daily'):
        """Send leaderboard data to client."""
        try:
            leaderboard_data = await self.get_leaderboard_data(period)
            await self.send(text_data=json.dumps({
                'type': 'leaderboard_data',
                'period': period,
                'leaderboard': leaderboard_data
            }))
        except Exception as exc:
            await self.send_error(f"Failed to get leaderboard: {str(exc)}")
    
    async def leaderboard_updated(self, event):
        """Handle leaderboard update broadcast."""
        await self.send(text_data=json.dumps({
            'type': 'leaderboard_updated',
            'leaderboard': event['leaderboard']
        }))
    
    async def send_error(self, error_message):
        """Send error message to client."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'error': error_message
        }))


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Dedicated notification WebSocket consumer.
    Provides real-time notification updates.
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope["user"]
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Create personal notification room
        self.room_group_name = f"notifications_user_{self.user.id}"
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial notifications
        await self.send_initial_notifications()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'mark_read':
                notification_id = data.get('notification_id')
                await self.mark_notification_read(notification_id)
            elif message_type == 'mark_all_read':
                await self.mark_all_notifications_read()
            else:
                await self.send_error("Unknown message type")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
    
    @database_sync_to_async
    def get_initial_notifications(self):
        """Get initial notifications for user."""
        try:
            return NotificationService.get_recent_notifications(self.user, limit=20)
        except:
            return []
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark notification as read."""
        try:
            return NotificationService.mark_as_read(self.user, notification_id)
        except:
            return False
    
    @database_sync_to_async
    def mark_all_notifications_read(self):
        """Mark all notifications as read."""
        try:
            return NotificationService.mark_all_read(self.user)
        except:
            return False
    
    async def send_initial_notifications(self):
        """Send initial notifications to client."""
        try:
            notifications = await self.get_initial_notifications()
            await self.send(text_data=json.dumps({
                'type': 'initial_notifications',
                'notifications': notifications
            }))
        except Exception as exc:
            await self.send_error(f"Failed to load notifications: {str(exc)}")
    
    async def new_notification(self, event):
        """Handle new notification broadcast."""
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'notification': event['notification']
        }))
    
    async def notification_read(self, event):
        """Handle notification read broadcast."""
        await self.send(text_data=json.dumps({
            'type': 'notification_read',
            'notification_id': event['notification_id']
        }))
    
    async def send_error(self, error_message):
        """Send error message to client."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'error': error_message
        }))
