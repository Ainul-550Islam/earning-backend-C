"""
Tenant Consumers - WebSocket/Real-time Communication

This module contains WebSocket consumers for real-time tenant communication
including notifications, updates, and live data synchronization.
"""

import json
import logging
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from .models_improved import Tenant, TenantAuditLog
from .permissions_improved import IsTenantMember
from .services_improved import tenant_security_service

logger = logging.getLogger(__name__)
User = get_user_model()


class TenantNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time tenant notifications.
    
    Handles live notifications, updates, and tenant-specific events.
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        try:
            # Get user from scope
            self.user = self.scope["user"]
            
            if not self.user or self.user.is_anonymous:
                await self.close(code=4001)
                return
            
            # Get tenant from URL parameters
            tenant_slug = self.scope["url_route"]["kwargs"].get("tenant_slug")
            if not tenant_slug:
                await self.close(code=4002)
                return
            
            # Get tenant and verify access
            self.tenant = await self.get_tenant(tenant_slug)
            if not self.tenant:
                await self.close(code=4003)
                return
            
            # Check if user has access to tenant
            if not await self.check_tenant_access():
                await self.close(code=4004)
                return
            
            # Create room name for this tenant
            self.room_group_name = f"tenant_{self.tenant.id}"
            
            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            # Add user to online users cache
            await self.add_user_to_online()
            
            # Accept connection
            await self.accept()
            
            # Send welcome message
            await self.send_notification({
                'type': 'connection',
                'message': 'Connected to tenant notifications',
                'timestamp': datetime.now().isoformat(),
                'user_id': self.user.id,
                'tenant_id': str(self.tenant.id),
            })
            
            logger.info(f"User {self.user.email} connected to tenant {self.tenant.name}")
            
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            await self.close(code=5000)
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        try:
            # Remove user from online users cache
            await self.remove_user_from_online()
            
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            logger.info(f"User {self.user.email} disconnected from tenant {self.tenant.name}")
            
        except Exception as e:
            logger.error(f"WebSocket disconnection error: {e}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            # Rate limiting check
            if not await self.check_rate_limit():
                await self.send_error('Rate limit exceeded')
                return
            
            # Handle different message types
            if message_type == 'ping':
                await self.handle_ping(text_data_json)
            elif message_type == 'mark_read':
                await self.handle_mark_read(text_data_json)
            elif message_type == 'get_online_users':
                await self.handle_get_online_users(text_data_json)
            elif message_type == 'typing':
                await self.handle_typing(text_data_json)
            else:
                await self.send_error('Unknown message type')
                
        except json.JSONDecodeError:
            await self.send_error('Invalid JSON format')
        except Exception as e:
            logger.error(f"WebSocket receive error: {e}")
            await self.send_error('Internal server error')
    
    async def tenant_notification(self, event):
        """Handle tenant notification broadcasts."""
        try:
            notification = event['notification']
            
            # Check if user should receive this notification
            if await self.should_receive_notification(notification):
                await self.send_text(json.dumps({
                    'type': 'notification',
                    'data': notification,
                    'timestamp': datetime.now().isoformat(),
                }))
                
        except Exception as e:
            logger.error(f"Notification broadcast error: {e}")
    
    async def tenant_update(self, event):
        """Handle tenant update broadcasts."""
        try:
            update_data = event['update']
            
            await self.send_text(json.dumps({
                'type': 'tenant_update',
                'data': update_data,
                'timestamp': datetime.now().isoformat(),
            }))
            
        except Exception as e:
            logger.error(f"Tenant update broadcast error: {e}")
    
    async def user_activity(self, event):
        """Handle user activity broadcasts."""
        try:
            activity_data = event['activity']
            
            # Don't send user's own activity back to them
            if activity_data.get('user_id') != self.user.id:
                await self.send_text(json.dumps({
                    'type': 'user_activity',
                    'data': activity_data,
                    'timestamp': datetime.now().isoformat(),
                }))
                
        except Exception as e:
            logger.error(f"User activity broadcast error: {e}")
    
    async def handle_ping(self, data):
        """Handle ping messages."""
        await self.send_text(json.dumps({
            'type': 'pong',
            'timestamp': datetime.now().isoformat(),
        }))
    
    async def handle_mark_read(self, data):
        """Handle mark as read messages."""
        try:
            notification_id = data.get('notification_id')
            if notification_id:
                # Mark notification as read in database
                await self.mark_notification_read(notification_id)
                
                await self.send_text(json.dumps({
                    'type': 'notification_read',
                    'notification_id': notification_id,
                    'timestamp': datetime.now().isoformat(),
                }))
                
        except Exception as e:
            logger.error(f"Mark read error: {e}")
            await self.send_error('Failed to mark notification as read')
    
    async def handle_get_online_users(self, data):
        """Handle get online users request."""
        try:
            online_users = await self.get_online_users()
            
            await self.send_text(json.dumps({
                'type': 'online_users',
                'data': online_users,
                'timestamp': datetime.now().isoformat(),
            }))
            
        except Exception as e:
            logger.error(f"Get online users error: {e}")
            await self.send_error('Failed to get online users')
    
    async def handle_typing(self, data):
        """Handle typing indicators."""
        try:
            # Broadcast typing indicator to other users
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_activity',
                    'activity': {
                        'user_id': self.user.id,
                        'user_email': self.user.email,
                        'action': 'typing',
                        'timestamp': datetime.now().isoformat(),
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Typing indicator error: {e}")
    
    async def send_notification(self, notification):
        """Send notification to client."""
        await self.send_text(json.dumps(notification))
    
    async def send_error(self, error_message):
        """Send error message to client."""
        await self.send_text(json.dumps({
            'type': 'error',
            'message': error_message,
            'timestamp': datetime.now().isoformat(),
        }))
    
    async def send_text(self, text):
        """Send text message to client."""
        await self.send(text_data=text)
    
    @database_sync_to_async
    def get_tenant(self, tenant_slug):
        """Get tenant by slug."""
        try:
            return Tenant.objects.get(
                slug=tenant_slug,
                is_active=True,
                is_deleted=False
            )
        except Tenant.DoesNotExist:
            return None
    
    @database_sync_to_async
    def check_tenant_access(self):
        """Check if user has access to tenant."""
        permission = IsTenantMember()
        return permission.has_permission(None, None) or self.tenant.owner == self.user
    
    @database_sync_to_async
    def add_user_to_online(self):
        """Add user to online users cache."""
        cache_key = f"tenant_online_users_{self.tenant.id}"
        online_users = cache.get(cache_key, {})
        
        online_users[str(self.user.id)] = {
            'user_id': self.user.id,
            'user_email': self.user.email,
            'last_seen': datetime.now().isoformat(),
            'channel_name': self.channel_name,
        }
        
        cache.set(cache_key, online_users, timeout=300)  # 5 minutes
    
    @database_sync_to_async
    def remove_user_from_online(self):
        """Remove user from online users cache."""
        cache_key = f"tenant_online_users_{self.tenant.id}"
        online_users = cache.get(cache_key, {})
        
        if str(self.user.id) in online_users:
            del online_users[str(self.user.id)]
            cache.set(cache_key, online_users, timeout=300)
    
    @database_sync_to_async
    def get_online_users(self):
        """Get list of online users."""
        cache_key = f"tenant_online_users_{self.tenant.id}"
        return cache.get(cache_key, {})
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark notification as read."""
        # This would be implemented based on your notification model
        pass
    
    @database_sync_to_async
    def should_receive_notification(self, notification):
        """Check if user should receive notification."""
        # Implement notification filtering logic
        return True
    
    @database_sync_to_async
    def check_rate_limit(self):
        """Check WebSocket rate limit."""
        cache_key = f"ws_rate_limit_{self.user.id}"
        count = cache.get(cache_key, 0)
        
        if count >= 100:  # 100 messages per minute
            return False
        
        cache.set(cache_key, count + 1, timeout=60)
        return True


class TenantAdminConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for tenant admin operations.
    
    Handles real-time admin updates, monitoring, and management.
    """
    
    async def connect(self):
        """Handle admin WebSocket connection."""
        try:
            self.user = self.scope["user"]
            
            if not self.user or not self.user.is_authenticated:
                await self.close(code=4001)
                return
            
            # Check if user is admin or tenant owner
            if not await self.check_admin_access():
                await self.close(code=4004)
                return
            
            # Get tenant from scope
            self.tenant = self.scope.get('tenant')
            if not self.tenant:
                await self.close(code=4003)
                return
            
            # Create admin room
            self.room_group_name = f"tenant_admin_{self.tenant.id}"
            
            # Join room
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            await self.accept()
            
            # Send admin dashboard data
            await self.send_admin_dashboard()
            
            logger.info(f"Admin {self.user.email} connected to tenant {self.tenant.name}")
            
        except Exception as e:
            logger.error(f"Admin WebSocket connection error: {e}")
            await self.close(code=5000)
    
    async def disconnect(self, close_code):
        """Handle admin WebSocket disconnection."""
        try:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            logger.info(f"Admin {self.user.email} disconnected from tenant {self.tenant.name}")
            
        except Exception as e:
            logger.error(f"Admin WebSocket disconnection error: {e}")
    
    async def receive(self, text_data):
        """Handle admin WebSocket messages."""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'get_stats':
                await self.handle_get_stats(text_data_json)
            elif message_type == 'get_users':
                await self.handle_get_users(text_data_json)
            elif message_type == 'suspend_user':
                await self.handle_suspend_user(text_data_json)
            elif message_type == 'update_settings':
                await self.handle_update_settings(text_data_json)
            elif message_type == 'get_audit_logs':
                await self.handle_get_audit_logs(text_data_json)
            else:
                await self.send_error('Unknown admin message type')
                
        except json.JSONDecodeError:
            await self.send_error('Invalid JSON format')
        except Exception as e:
            logger.error(f"Admin WebSocket receive error: {e}")
            await self.send_error('Internal server error')
    
    async def handle_get_stats(self, data):
        """Handle get stats request."""
        try:
            stats = await self.get_tenant_stats()
            
            await self.send_text(json.dumps({
                'type': 'stats',
                'data': stats,
                'timestamp': datetime.now().isoformat(),
            }))
            
        except Exception as e:
            logger.error(f"Get stats error: {e}")
            await self.send_error('Failed to get stats')
    
    async def handle_get_users(self, data):
        """Handle get users request."""
        try:
            users = await self.get_tenant_users(data.get('page', 1), data.get('page_size', 20))
            
            await self.send_text(json.dumps({
                'type': 'users',
                'data': users,
                'timestamp': datetime.now().isoformat(),
            }))
            
        except Exception as e:
            logger.error(f"Get users error: {e}")
            await self.send_error('Failed to get users')
    
    async def handle_suspend_user(self, data):
        """Handle suspend user request."""
        try:
            user_id = data.get('user_id')
            if user_id:
                await self.suspend_tenant_user(user_id)
                
                await self.send_text(json.dumps({
                    'type': 'user_suspended',
                    'user_id': user_id,
                    'timestamp': datetime.now().isoformat(),
                }))
                
        except Exception as e:
            logger.error(f"Suspend user error: {e}")
            await self.send_error('Failed to suspend user')
    
    async def handle_update_settings(self, data):
        """Handle update settings request."""
        try:
            settings_data = data.get('settings', {})
            await self.update_tenant_settings(settings_data)
            
            await self.send_text(json.dumps({
                'type': 'settings_updated',
                'data': settings_data,
                'timestamp': datetime.now().isoformat(),
            }))
            
        except Exception as e:
            logger.error(f"Update settings error: {e}")
            await self.send_error('Failed to update settings')
    
    async def handle_get_audit_logs(self, data):
        """Handle get audit logs request."""
        try:
            logs = await self.get_audit_logs(
                data.get('page', 1),
                data.get('page_size', 20),
                data.get('filters', {})
            )
            
            await self.send_text(json.dumps({
                'type': 'audit_logs',
                'data': logs,
                'timestamp': datetime.now().isoformat(),
            }))
            
        except Exception as e:
            logger.error(f"Get audit logs error: {e}")
            await self.send_error('Failed to get audit logs')
    
    async def send_admin_dashboard(self):
        """Send initial admin dashboard data."""
        try:
            dashboard_data = await self.get_admin_dashboard_data()
            
            await self.send_text(json.dumps({
                'type': 'admin_dashboard',
                'data': dashboard_data,
                'timestamp': datetime.now().isoformat(),
            }))
            
        except Exception as e:
            logger.error(f"Send admin dashboard error: {e}")
    
    async def send_error(self, error_message):
        """Send error message to client."""
        await self.send_text(json.dumps({
            'type': 'error',
            'message': error_message,
            'timestamp': datetime.now().isoformat(),
        }))
    
    async def send_text(self, text):
        """Send text message to client."""
        await self.send(text_data=text)
    
    @database_sync_to_async
    def check_admin_access(self):
        """Check if user has admin access."""
        return self.user.is_superuser or self.user.is_staff
    
    @database_sync_to_async
    def get_tenant_stats(self):
        """Get tenant statistics."""
        # Implement stats collection
        return {
            'total_users': 0,
            'active_users': 0,
            'total_revenue': 0,
            'monthly_revenue': 0,
            'api_calls': 0,
            'storage_usage': 0,
        }
    
    @database_sync_to_async
    def get_tenant_users(self, page, page_size):
        """Get tenant users with pagination."""
        # Implement user listing
        return {
            'users': [],
            'total_count': 0,
            'page': page,
            'page_size': page_size,
        }
    
    @database_sync_to_async
    def suspend_tenant_user(self, user_id):
        """Suspend tenant user."""
        # Implement user suspension
        pass
    
    @database_sync_to_async
    def update_tenant_settings(self, settings_data):
        """Update tenant settings."""
        # Implement settings update
        pass
    
    @database_sync_to_async
    def get_audit_logs(self, page, page_size, filters):
        """Get audit logs with filtering."""
        # Implement audit log retrieval
        return {
            'logs': [],
            'total_count': 0,
            'page': page,
            'page_size': page_size,
        }
    
    @database_sync_to_async
    def get_admin_dashboard_data(self):
        """Get admin dashboard data."""
        # Implement dashboard data collection
        return {
            'stats': {},
            'recent_activity': [],
            'alerts': [],
            'system_health': {},
        }


class TenantSupportConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for tenant support chat.
    
    Handles real-time support communication between tenants and support staff.
    """
    
    async def connect(self):
        """Handle support WebSocket connection."""
        try:
            self.user = self.scope["user"]
            
            if not self.user or not self.user.is_authenticated:
                await self.close(code=4001)
                return
            
            # Get tenant from scope
            self.tenant = self.scope.get('tenant')
            if not self.tenant:
                await self.close(code=4003)
                return
            
            # Check if user has support access
            if not await self.check_support_access():
                await self.close(code=4004)
                return
            
            # Create support room
            self.room_group_name = f"tenant_support_{self.tenant.id}"
            
            # Join room
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            await self.accept()
            
            # Send support chat history
            await self.send_chat_history()
            
            logger.info(f"User {self.user.email} connected to support for tenant {self.tenant.name}")
            
        except Exception as e:
            logger.error(f"Support WebSocket connection error: {e}")
            await self.close(code=5000)
    
    async def disconnect(self, close_code):
        """Handle support WebSocket disconnection."""
        try:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            logger.info(f"User {self.user.email} disconnected from support for tenant {self.tenant.name}")
            
        except Exception as e:
            logger.error(f"Support WebSocket disconnection error: {e}")
    
    async def receive(self, text_data):
        """Handle support WebSocket messages."""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'message':
                await self.handle_message(text_data_json)
            elif message_type == 'typing':
                await self.handle_typing(text_data_json)
            elif message_type == 'get_history':
                await self.handle_get_history(text_data_json)
            else:
                await self.send_error('Unknown support message type')
                
        except json.JSONDecodeError:
            await self.send_error('Invalid JSON format')
        except Exception as e:
            logger.error(f"Support WebSocket receive error: {e}")
            await self.send_error('Internal server error')
    
    async def handle_message(self, data):
        """Handle chat message."""
        try:
            message = data.get('message', '').strip()
            if not message:
                await self.send_error('Message cannot be empty')
                return
            
            # Save message to database
            chat_message = await self.save_chat_message(message)
            
            # Broadcast message to all support participants
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': {
                        'id': chat_message['id'],
                        'message': message,
                        'sender': self.user.email,
                        'sender_id': self.user.id,
                        'timestamp': chat_message['timestamp'],
                        'is_support': await self.is_support_user(),
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Handle message error: {e}")
            await self.send_error('Failed to send message')
    
    async def handle_typing(self, data):
        """Handle typing indicator."""
        try:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_indicator',
                    'data': {
                        'user_id': self.user.id,
                        'user_email': self.user.email,
                        'is_typing': True,
                        'timestamp': datetime.now().isoformat(),
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Typing indicator error: {e}")
    
    async def handle_get_history(self, data):
        """Handle get chat history request."""
        try:
            history = await self.get_chat_history(data.get('limit', 50))
            
            await self.send_text(json.dumps({
                'type': 'chat_history',
                'data': history,
                'timestamp': datetime.now().isoformat(),
            }))
            
        except Exception as e:
            logger.error(f"Get chat history error: {e}")
            await self.send_error('Failed to get chat history')
    
    async def chat_message(self, event):
        """Handle chat message broadcasts."""
        message = event['message']
        
        # Don't send user's own message back to them
        if message['sender_id'] != self.user.id:
            await self.send_text(json.dumps({
                'type': 'chat_message',
                'data': message,
                'timestamp': datetime.now().isoformat(),
            }))
    
    async def typing_indicator(self, event):
        """Handle typing indicator broadcasts."""
        typing_data = event['data']
        
        # Don't send user's own typing indicator back to them
        if typing_data['user_id'] != self.user.id:
            await self.send_text(json.dumps({
                'type': 'typing_indicator',
                'data': typing_data,
                'timestamp': datetime.now().isoformat(),
            }))
    
    async def send_chat_history(self):
        """Send initial chat history."""
        try:
            history = await self.get_chat_history(20)
            
            await self.send_text(json.dumps({
                'type': 'chat_history',
                'data': history,
                'timestamp': datetime.now().isoformat(),
            }))
            
        except Exception as e:
            logger.error(f"Send chat history error: {e}")
    
    async def send_error(self, error_message):
        """Send error message to client."""
        await self.send_text(json.dumps({
            'type': 'error',
            'message': error_message,
            'timestamp': datetime.now().isoformat(),
        }))
    
    async def send_text(self, text):
        """Send text message to client."""
        await self.send(text_data=text)
    
    @database_sync_to_async
    def check_support_access(self):
        """Check if user has support access."""
        return self.tenant.owner == self.user or self.user.is_staff
    
    @database_sync_to_async
    def save_chat_message(self, message):
        """Save chat message to database."""
        # Implement chat message saving
        return {
            'id': 'temp_id',
            'message': message,
            'timestamp': datetime.now().isoformat(),
        }
    
    @database_sync_to_async
    def is_support_user(self):
        """Check if user is support staff."""
        return self.user.is_staff
    
    @database_sync_to_async
    def get_chat_history(self, limit):
        """Get chat history."""
        # Implement chat history retrieval
        return {
            'messages': [],
            'total_count': 0,
        }
