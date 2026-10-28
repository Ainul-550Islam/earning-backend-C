"""
Backup Module WebSocket Consumers
Real-time backup monitoring and notifications via WebSockets
"""
from django.db import models

import json
import asyncio
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from .models import Backup, BackupLog, BackupAlert
from .exceptions import BackupException
import logging

logger = logging.getLogger(__name__)


class BackupStatusConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time backup status updates
    """
    
    async def connect(self):
        """
        Handle WebSocket connection
        """
        # Check user authentication
        if self.scope["user"].is_anonymous:
            await self.close()
            return
        
        # Check user permissions
        if not await self._has_backup_permission():
            await self.close()
            return
        
        # Create unique group name for this user
        self.user_group_name = f"backup_status_{self.scope['user'].id}"
        
        # Join user group
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        
        # Join global backup status group if user is admin
        if await self._is_backup_admin():
            await self.channel_layer.group_add(
                "backup_status_global",
                self.channel_name
            )
        
        await self.accept()
        
        # Send initial status
        await self._send_initial_status()
    
    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection
        """
        # Leave user group
        await self.channel_layer.group_discard(
            self.user_group_name,
            self.channel_name
        )
        
        # Leave global group if user is admin
        if await self._is_backup_admin():
            await self.channel_layer.group_discard(
                "backup_status_global",
                self.channel_name
            )
    
    async def receive(self, text_data):
        """
        Handle incoming WebSocket messages
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'subscribe_backup':
                backup_id = data.get('backup_id')
                if backup_id:
                    await self._subscribe_to_backup(backup_id)
            
            elif message_type == 'unsubscribe_backup':
                backup_id = data.get('backup_id')
                if backup_id:
                    await self._unsubscribe_from_backup(backup_id)
            
            elif message_type == 'get_backup_status':
                backup_id = data.get('backup_id')
                if backup_id:
                    await self._send_backup_status(backup_id)
            
            elif message_type == 'get_active_backups':
                await self._send_active_backups()
            
            else:
                await self._send_error('Unknown message type')
                
        except json.JSONDecodeError:
            await self._send_error('Invalid JSON')
        except Exception as e:
            logger.error(f"Error in receive: {e}")
            await self._send_error('Internal server error')
    
    async def backup_status_update(self, event):
        """
        Handle backup status update event
        """
        await self._send_message({
            'type': 'backup_status_update',
            'backup': event['backup']
        })
    
    async def backup_completed(self, event):
        """
        Handle backup completion event
        """
        await self._send_message({
            'type': 'backup_completed',
            'backup': event['backup']
        })
    
    async def backup_failed(self, event):
        """
        Handle backup failure event
        """
        await self._send_message({
            'type': 'backup_failed',
            'backup': event['backup'],
            'error': event.get('error')
        })
    
    async def backup_alert(self, event):
        """
        Handle backup alert event
        """
        await self._send_message({
            'type': 'backup_alert',
            'alert': event['alert']
        })
    
    async def _send_message(self, message):
        """
        Send message to WebSocket
        """
        await self.send(text_data=json.dumps(message))
    
    async def _send_error(self, error_message):
        """
        Send error message to WebSocket
        """
        await self._send_message({
            'type': 'error',
            'message': error_message
        })
    
    async def _send_initial_status(self):
        """
        Send initial backup status to newly connected client
        """
        try:
            # Get recent backups
            recent_backups = await self._get_recent_backups()
            
            # Get active backups
            active_backups = await self._get_active_backups()
            
            # Get recent alerts
            recent_alerts = await self._get_recent_alerts()
            
            await self._send_message({
                'type': 'initial_status',
                'recent_backups': recent_backups,
                'active_backups': active_backups,
                'recent_alerts': recent_alerts,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error sending initial status: {e}")
            await self._send_error('Failed to load initial status')
    
    async def _subscribe_to_backup(self, backup_id):
        """
        Subscribe to specific backup updates
        """
        group_name = f"backup_{backup_id}"
        await self.channel_layer.group_add(
            group_name,
            self.channel_name
        )
        
        await self._send_message({
            'type': 'subscribed',
            'backup_id': backup_id
        })
    
    async def _unsubscribe_from_backup(self, backup_id):
        """
        Unsubscribe from specific backup updates
        """
        group_name = f"backup_{backup_id}"
        await self.channel_layer.group_discard(
            group_name,
            self.channel_name
        )
        
        await self._send_message({
            'type': 'unsubscribed',
            'backup_id': backup_id
        })
    
    async def _send_backup_status(self, backup_id):
        """
        Send status for specific backup
        """
        try:
            backup = await self._get_backup_by_id(backup_id)
            if backup:
                await self._send_message({
                    'type': 'backup_status',
                    'backup': backup
                })
            else:
                await self._send_error('Backup not found')
        except Exception as e:
            logger.error(f"Error sending backup status: {e}")
            await self._send_error('Failed to get backup status')
    
    async def _send_active_backups(self):
        """
        Send list of active backups
        """
        try:
            active_backups = await self._get_active_backups()
            await self._send_message({
                'type': 'active_backups',
                'backups': active_backups
            })
        except Exception as e:
            logger.error(f"Error sending active backups: {e}")
            await self._send_error('Failed to get active backups')
    
    @database_sync_to_async
    def _has_backup_permission(self):
        """
        Check if user has backup permission
        """
        from .permissions import has_backup_group_permission
        return has_backup_group_permission(self.scope["user"], 'backup_viewer')
    
    @database_sync_to_async
    def _is_backup_admin(self):
        """
        Check if user is backup admin
        """
        from .permissions import has_backup_group_permission
        return has_backup_group_permission(self.scope["user"], 'backup_admin')
    
    @database_sync_to_async
    def _get_recent_backups(self):
        """
        Get recent backups for user
        """
        user = self.scope["user"]
        if user.is_superuser:
            backups = Backup.objects.all()
        else:
            backups = Backup.objects.filter(created_by=user)
        
        recent_backups = backups.order_by('-created_at')[:10]
        
        return [
            {
                'id': str(backup.id),
                'name': backup.name,
                'status': backup.status,
                'created_at': backup.created_at.isoformat(),
                'size': backup.file_size,
                'type': backup.backup_type,
                'progress': backup.progress
            }
            for backup in recent_backups
        ]
    
    @database_sync_to_async
    def _get_active_backups(self):
        """
        Get active backups
        """
        user = self.scope["user"]
        if user.is_superuser:
            backups = Backup.objects.filter(status__in=['pending', 'running'])
        else:
            backups = Backup.objects.filter(
                status__in=['pending', 'running'],
                created_by=user
            )
        
        return [
            {
                'id': str(backup.id),
                'name': backup.name,
                'status': backup.status,
                'progress': backup.progress,
                'started_at': backup.started_at.isoformat() if backup.started_at else None,
                'estimated_completion': backup.estimated_completion.isoformat() if backup.estimated_completion else None
            }
            for backup in backups
        ]
    
    @database_sync_to_async
    def _get_recent_alerts(self):
        """
        Get recent alerts for user
        """
        user = self.scope["user"]
        if user.is_superuser:
            alerts = BackupAlert.objects.all()
        else:
            alerts = BackupAlert.objects.filter(
                backup__created_by=user
            ).distinct()
        
        recent_alerts = alerts.filter(is_resolved=False).order_by('-created_at')[:5]
        
        return [
            {
                'id': str(alert.id),
                'alert_type': alert.alert_type,
                'message': alert.message,
                'severity': alert.severity,
                'created_at': alert.created_at.isoformat(),
                'backup_id': str(alert.backup.id) if alert.backup else None
            }
            for alert in recent_alerts
        ]
    
    @database_sync_to_async
    def _get_backup_by_id(self, backup_id):
        """
        Get backup by ID
        """
        try:
            backup = Backup.objects.get(id=backup_id)
            user = self.scope["user"]
            
            # Check permission
            if user.is_superuser or backup.created_by == user:
                return {
                    'id': str(backup.id),
                    'name': backup.name,
                    'status': backup.status,
                    'progress': backup.progress,
                    'created_at': backup.created_at.isoformat(),
                    'started_at': backup.started_at.isoformat() if backup.started_at else None,
                    'completed_at': backup.completed_at.isoformat() if backup.completed_at else None,
                    'size': backup.file_size,
                    'type': backup.backup_type,
                    'storage_type': backup.storage_type,
                    'health_score': backup.health_score,
                    'error_message': backup.error_message
                }
            else:
                return None
        except Backup.DoesNotExist:
            return None


class BackupLogConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time backup log streaming
    """
    
    async def connect(self):
        """
        Handle WebSocket connection
        """
        # Check user authentication
        if self.scope["user"].is_anonymous:
            await self.close()
            return
        
        # Check user permissions
        if not await self._has_backup_permission():
            await self.close()
            return
        
        # Create unique group name for this user
        self.user_group_name = f"backup_logs_{self.scope['user'].id}"
        
        # Join user group
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial log count
        await self._send_initial_log_info()
    
    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection
        """
        await self.channel_layer.group_discard(
            self.user_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """
        Handle incoming WebSocket messages
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'subscribe_logs':
                backup_id = data.get('backup_id')
                if backup_id:
                    await self._subscribe_to_backup_logs(backup_id)
            
            elif message_type == 'get_logs':
                backup_id = data.get('backup_id')
                limit = data.get('limit', 50)
                if backup_id:
                    await self._send_backup_logs(backup_id, limit)
            
            elif message_type == 'get_log_stats':
                backup_id = data.get('backup_id')
                if backup_id:
                    await self._send_log_stats(backup_id)
            
            else:
                await self._send_error('Unknown message type')
                
        except json.JSONDecodeError:
            await self._send_error('Invalid JSON')
        except Exception as e:
            logger.error(f"Error in receive: {e}")
            await self._send_error('Internal server error')
    
    async def backup_log_created(self, event):
        """
        Handle new log entry event
        """
        await self._send_message({
            'type': 'new_log',
            'log': event['log']
        })
    
    async def _send_message(self, message):
        """
        Send message to WebSocket
        """
        await self.send(text_data=json.dumps(message))
    
    async def _send_error(self, error_message):
        """
        Send error message to WebSocket
        """
        await self._send_message({
            'type': 'error',
            'message': error_message
        })
    
    async def _send_initial_log_info(self):
        """
        Send initial log information
        """
        try:
            total_logs = await self._get_total_log_count()
            recent_logs = await self._get_recent_logs(10)
            
            await self._send_message({
                'type': 'initial_log_info',
                'total_logs': total_logs,
                'recent_logs': recent_logs,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error sending initial log info: {e}")
            await self._send_error('Failed to load initial log info')
    
    async def _subscribe_to_backup_logs(self, backup_id):
        """
        Subscribe to logs for specific backup
        """
        group_name = f"backup_logs_{backup_id}"
        await self.channel_layer.group_add(
            group_name,
            self.channel_name
        )
        
        await self._send_message({
            'type': 'subscribed_logs',
            'backup_id': backup_id
        })
    
    async def _send_backup_logs(self, backup_id, limit=50):
        """
        Send logs for specific backup
        """
        try:
            logs = await self._get_backup_logs(backup_id, limit)
            await self._send_message({
                'type': 'backup_logs',
                'backup_id': backup_id,
                'logs': logs
            })
        except Exception as e:
            logger.error(f"Error sending backup logs: {e}")
            await self._send_error('Failed to get backup logs')
    
    async def _send_log_stats(self, backup_id):
        """
        Send log statistics for backup
        """
        try:
            stats = await self._get_log_stats(backup_id)
            await self._send_message({
                'type': 'log_stats',
                'backup_id': backup_id,
                'stats': stats
            })
        except Exception as e:
            logger.error(f"Error sending log stats: {e}")
            await self._send_error('Failed to get log stats')
    
    @database_sync_to_async
    def _has_backup_permission(self):
        """
        Check if user has backup permission
        """
        from .permissions import has_backup_group_permission
        return has_backup_group_permission(self.scope["user"], 'backup_viewer')
    
    @database_sync_to_async
    def _get_total_log_count(self):
        """
        Get total log count for user
        """
        user = self.scope["user"]
        if user.is_superuser:
            return BackupLog.objects.count()
        else:
            return BackupLog.objects.filter(
                backup__created_by=user
            ).count()
    
    @database_sync_to_async
    def _get_recent_logs(self, limit=10):
        """
        Get recent logs for user
        """
        user = self.scope["user"]
        if user.is_superuser:
            logs = BackupLog.objects.all()
        else:
            logs = BackupLog.objects.filter(
                backup__created_by=user
            )
        
        recent_logs = logs.order_by('-timestamp')[:limit]
        
        return [
            {
                'id': str(log.id),
                'level': log.level,
                'message': log.message,
                'timestamp': log.timestamp.isoformat(),
                'action': log.action,
                'category': log.category,
                'backup_id': str(log.backup.id) if log.backup else None
            }
            for log in recent_logs
        ]
    
    @database_sync_to_async
    def _get_backup_logs(self, backup_id, limit=50):
        """
        Get logs for specific backup
        """
        try:
            backup = Backup.objects.get(id=backup_id)
            user = self.scope["user"]
            
            # Check permission
            if not (user.is_superuser or backup.created_by == user):
                return []
            
            logs = BackupLog.objects.filter(backup=backup).order_by('-timestamp')[:limit]
            
            return [
                {
                    'id': str(log.id),
                    'level': log.level,
                    'message': log.message,
                    'timestamp': log.timestamp.isoformat(),
                    'action': log.action,
                    'category': log.category,
                    'duration': log.duration,
                    'memory_usage': log.memory_usage,
                    'cpu_usage': log.cpu_usage
                }
                for log in logs
            ]
        except Backup.DoesNotExist:
            return []
    
    @database_sync_to_async
    def _get_log_stats(self, backup_id):
        """
        Get log statistics for backup
        """
        try:
            backup = Backup.objects.get(id=backup_id)
            user = self.scope["user"]
            
            # Check permission
            if not (user.is_superuser or backup.created_by == user):
                return {}
            
            logs = BackupLog.objects.filter(backup=backup)
            
            # Calculate statistics
            stats = {
                'total_logs': logs.count(),
                'by_level': {},
                'by_category': {},
                'by_action': {},
                'avg_duration': 0,
                'max_memory_usage': 0,
                'max_cpu_usage': 0
            }
            
            # Count by level
            for log in logs.values('level').annotate(count=models.Count('level')):
                stats['by_level'][log['level']] = log['count']
            
            # Count by category
            for log in logs.values('category').annotate(count=models.Count('category')):
                stats['by_category'][log['category']] = log['count']
            
            # Count by action
            for log in logs.values('action').annotate(count=models.Count('action')):
                stats['by_action'][log['action']] = log['count']
            
            # Performance stats
            duration_logs = logs.filter(duration__isnull=False)
            if duration_logs.exists():
                stats['avg_duration'] = duration_logs.aggregate(
                    avg=models.Avg('duration')
                )['avg_duration'] or 0
            
            memory_logs = logs.filter(memory_usage__isnull=False)
            if memory_logs.exists():
                stats['max_memory_usage'] = memory_logs.aggregate(
                    max=models.Max('memory_usage')
                )['max_memory_usage'] or 0
            
            cpu_logs = logs.filter(cpu_usage__isnull=False)
            if cpu_logs.exists():
                stats['max_cpu_usage'] = cpu_logs.aggregate(
                    max=models.Max('cpu_usage')
                )['max_cpu_usage'] or 0
            
            return stats
            
        except Backup.DoesNotExist:
            return {}


class BackupAnalyticsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time backup analytics
    """
    
    async def connect(self):
        """
        Handle WebSocket connection
        """
        # Check user authentication
        if self.scope["user"].is_anonymous:
            await self.close()
            return
        
        # Check user permissions (admin only)
        if not await self._is_backup_admin():
            await self.close()
            return
        
        # Join analytics group
        await self.channel_layer.group_add(
            "backup_analytics",
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial analytics
        await self._send_initial_analytics()
    
    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection
        """
        await self.channel_layer.group_discard(
            "backup_analytics",
            self.channel_name
        )
    
    async def receive(self, text_data):
        """
        Handle incoming WebSocket messages
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'get_analytics':
                period = data.get('period', '24h')
                await self._send_analytics(period)
            
            elif message_type == 'get_storage_stats':
                await self._send_storage_stats()
            
            elif message_type == 'get_performance_metrics':
                await self._send_performance_metrics()
            
            else:
                await self._send_error('Unknown message type')
                
        except json.JSONDecodeError:
            await self._send_error('Invalid JSON')
        except Exception as e:
            logger.error(f"Error in receive: {e}")
            await self._send_error('Internal server error')
    
    async def analytics_updated(self, event):
        """
        Handle analytics update event
        """
        await self._send_message({
            'type': 'analytics_updated',
            'data': event['data']
        })
    
    async def _send_message(self, message):
        """
        Send message to WebSocket
        """
        await self.send(text_data=json.dumps(message))
    
    async def _send_error(self, error_message):
        """
        Send error message to WebSocket
        """
        await self._send_message({
            'type': 'error',
            'message': error_message
        })
    
    async def _send_initial_analytics(self):
        """
        Send initial analytics data
        """
        try:
            analytics = await self._get_analytics('24h')
            storage_stats = await self._get_storage_stats()
            performance_metrics = await self._get_performance_metrics()
            
            await self._send_message({
                'type': 'initial_analytics',
                'analytics': analytics,
                'storage_stats': storage_stats,
                'performance_metrics': performance_metrics,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error sending initial analytics: {e}")
            await self._send_error('Failed to load initial analytics')
    
    async def _send_analytics(self, period='24h'):
        """
        Send analytics data for specified period
        """
        try:
            analytics = await self._get_analytics(period)
            await self._send_message({
                'type': 'analytics',
                'period': period,
                'data': analytics
            })
        except Exception as e:
            logger.error(f"Error sending analytics: {e}")
            await self._send_error('Failed to get analytics')
    
    async def _send_storage_stats(self):
        """
        Send storage statistics
        """
        try:
            storage_stats = await self._get_storage_stats()
            await self._send_message({
                'type': 'storage_stats',
                'data': storage_stats
            })
        except Exception as e:
            logger.error(f"Error sending storage stats: {e}")
            await self._send_error('Failed to get storage stats')
    
    async def _send_performance_metrics(self):
        """
        Send performance metrics
        """
        try:
            performance_metrics = await self._get_performance_metrics()
            await self._send_message({
                'type': 'performance_metrics',
                'data': performance_metrics
            })
        except Exception as e:
            logger.error(f"Error sending performance metrics: {e}")
            await self._send_error('Failed to get performance metrics')
    
    @database_sync_to_async
    def _is_backup_admin(self):
        """
        Check if user is backup admin
        """
        from .permissions import has_backup_group_permission
        return has_backup_group_permission(self.scope["user"], 'backup_admin')
    
    @database_sync_to_async
    def _get_analytics(self, period='24h'):
        """
        Get analytics data for specified period
        """
        # This would implement actual analytics calculation
        # For now, return placeholder data
        return {
            'total_backups': 0,
            'successful_backups': 0,
            'failed_backups': 0,
            'average_duration': 0,
            'total_size': 0,
            'by_type': {},
            'by_storage': {},
            'success_rate': 0,
            'period': period
        }
    
    @database_sync_to_async
    def _get_storage_stats(self):
        """
        Get storage statistics
        """
        # This would implement actual storage statistics
        # For now, return placeholder data
        return {
            'total_storage_used': 0,
            'total_storage_available': 0,
            'storage_locations': [],
            'growth_rate': 0,
            'compression_ratio': 0
        }
    
    @database_sync_to_async
    def _get_performance_metrics(self):
        """
        Get performance metrics
        """
        # This would implement actual performance metrics
        # For now, return placeholder data
        return {
            'average_backup_time': 0,
            'peak_concurrent_backups': 0,
            'system_load': 0,
            'memory_usage': 0,
            'disk_io': 0,
            'network_throughput': 0
        }


# Utility functions for WebSocket consumers
async def send_backup_update(backup_id, update_type, data):
    """
    Send backup update to relevant WebSocket consumers
    """
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    
    # Send to specific backup group
    await channel_layer.group_send(
        f"backup_{backup_id}",
        {
            'type': update_type,
            'backup': data
        }
    )
    
    # Send to global status group
    await channel_layer.group_send(
        "backup_status_global",
        {
            'type': update_type,
            'backup': data
        }
    )


async def send_log_update(backup_id, log_data):
    """
    Send log update to relevant WebSocket consumers
    """
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    
    # Send to backup logs group
    await channel_layer.group_send(
        f"backup_logs_{backup_id}",
        {
            'type': 'backup_log_created',
            'log': log_data
        }
    )


async def send_analytics_update(analytics_data):
    """
    Send analytics update to admin consumers
    """
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    
    # Send to analytics group
    await channel_layer.group_send(
        "backup_analytics",
        {
            'type': 'analytics_updated',
            'data': analytics_data
        }
    )


# Export consumers
__all__ = [
    'BackupStatusConsumer',
    'BackupLogConsumer', 
    'BackupAnalyticsConsumer',
    'send_backup_update',
    'send_log_update',
    'send_analytics_update',
]
