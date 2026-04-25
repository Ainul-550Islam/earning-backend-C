"""
WebSocket Consumers for Offer Routing System

This module provides WebSocket consumers for real-time routing decisions,
including live routing stats, cap monitoring, and dashboard updates.
"""

import json
import asyncio
import logging
from datetime import datetime, timedelta
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import (
    RoutingDecisionLog, OfferRoutingCap, UserOfferCap,
    RoutingABTest, RoutePerformanceStat, RoutingInsight
)
from .services.analytics import analytics_service
from .services.monitoring import monitoring_service

User = get_user_model()
logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()


class RoutingDashboardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time routing dashboard.
    
    Provides live updates for routing statistics, performance metrics,
    and system health monitoring.
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        try:
            # Get user from scope
            user = self.scope["user"]
            
            if not user or not user.is_authenticated:
                await self.close(code=4001)
                return
            
            # Get tenant from user
            tenant_id = getattr(user, 'tenant_id', None)
            
            # Join tenant-specific group
            group_name = f"routing_dashboard_{tenant_id}"
            await self.channel_layer.group_add(
                group_name,
                self.channel_name
            )
            
            # Send initial data
            await self.send_initial_dashboard_data(tenant_id)
            
            # Start periodic updates
            asyncio.create_task(self.start_periodic_updates(tenant_id))
            
            logger.info(f"Dashboard WebSocket connected for tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Error in dashboard connect: {e}")
            await self.close(code=4000)
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        try:
            user = self.scope["user"]
            tenant_id = getattr(user, 'tenant_id', None)
            
            # Leave tenant group
            group_name = f"routing_dashboard_{tenant_id}"
            await self.channel_layer.group_discard(
                group_name,
                self.channel_name
            )
            
            logger.info(f"Dashboard WebSocket disconnected for tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Error in dashboard disconnect: {e}")
    
    async def send_initial_dashboard_data(self, tenant_id):
        """Send initial dashboard data to client."""
        try:
            # Get current stats
            stats = await self.get_dashboard_stats(tenant_id)
            
            await self.send(text_data=json.dumps({
                'type': 'initial_data',
                'data': stats,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error sending initial data: {e}")
    
    async def start_periodic_updates(self, tenant_id):
        """Start periodic updates for dashboard."""
        while True:
            try:
                # Get updated stats
                stats = await self.get_dashboard_stats(tenant_id)
                
                await self.send(text_data=json.dumps({
                    'type': 'periodic_update',
                    'data': stats,
                    'timestamp': timezone.now().isoformat()
                }))
                
                # Wait 30 seconds
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in periodic update: {e}")
                await asyncio.sleep(30)
    
    @database_sync_to_async
    def get_dashboard_stats(self, tenant_id):
        """Get dashboard statistics."""
        try:
            # Get today's stats
            today = timezone.now().date()
            
            # Routing decisions today
            decisions_today = RoutingDecisionLog.objects.filter(
                created_at__date=today
            ).count()
            
            # Active routes
            active_routes = OfferRoute.objects.filter(
                tenant_id=tenant_id,
                is_active=True
            ).count()
            
            # Active A/B tests
            active_tests = RoutingABTest.objects.filter(
                tenant_id=tenant_id,
                is_active=True
            ).count()
            
            # Performance metrics
            avg_response_time = RoutePerformanceStat.objects.filter(
                tenant_id=tenant_id,
                date=today
            ).aggregate(avg_response_time=models.Avg('response_time_ms'))
            
            # Cap alerts
            cap_alerts = RoutingInsight.objects.filter(
                tenant_id=tenant_id,
                insight_type='cap_alert',
                is_resolved=False
            ).count()
            
            return {
                'decisions_today': decisions_today,
                'active_routes': active_routes,
                'active_tests': active_tests,
                'avg_response_time': avg_response_time or 0,
                'cap_alerts': cap_alerts,
                'system_health': monitoring_service.get_system_health()
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {e}")
            return {}


class CapMonitorConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time cap monitoring.
    
    Provides live updates for cap usage, alerts,
    and threshold monitoring.
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        try:
            user = self.scope["user"]
            
            if not user or not user.is_authenticated:
                await self.close(code=4001)
                return
            
            tenant_id = getattr(user, 'tenant_id', None)
            
            # Join cap monitoring group
            group_name = f"cap_monitor_{tenant_id}"
            await self.channel_layer.group_add(
                group_name,
                self.channel_name
            )
            
            # Send initial cap data
            await self.send_initial_cap_data(tenant_id)
            
            # Start cap monitoring
            asyncio.create_task(self.start_cap_monitoring(tenant_id))
            
            logger.info(f"Cap monitor WebSocket connected for tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Error in cap monitor connect: {e}")
            await self.close(code=4000)
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        try:
            user = self.scope["user"]
            tenant_id = getattr(user, 'tenant_id', None)
            
            # Leave cap monitoring group
            group_name = f"cap_monitor_{tenant_id}"
            await self.channel_layer.group_discard(
                group_name,
                self.channel_name
            )
            
            logger.info(f"Cap monitor WebSocket disconnected for tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Error in cap monitor disconnect: {e}")
    
    async def send_initial_cap_data(self, tenant_id):
        """Send initial cap data to client."""
        try:
            # Get current cap status
            cap_data = await self.get_cap_status(tenant_id)
            
            await self.send(text_data=json.dumps({
                'type': 'initial_cap_data',
                'data': cap_data,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error sending initial cap data: {e}")
    
    async def start_cap_monitoring(self, tenant_id):
        """Start real-time cap monitoring."""
        while True:
            try:
                # Get updated cap status
                cap_data = await self.get_cap_status(tenant_id)
                
                # Check for alerts
                alerts = await self.check_cap_alerts(cap_data)
                
                await self.send(text_data=json.dumps({
                    'type': 'cap_update',
                    'data': cap_data,
                    'alerts': alerts,
                    'timestamp': timezone.now().isoformat()
                }))
                
                # Wait 10 seconds for real-time monitoring
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Error in cap monitoring: {e}")
                await asyncio.sleep(10)
    
    @database_sync_to_async
    def get_cap_status(self, tenant_id):
        """Get current cap status."""
        try:
            # Get global caps
            global_caps = OfferRoutingCap.objects.filter(
                tenant_id=tenant_id,
                is_active=True
            ).select_related('offer')
            
            # Get user caps
            user_caps = UserOfferCap.objects.filter(
                user__tenant_id=tenant_id
            ).select_related('user', 'offer')
            
            cap_data = {
                'global_caps': [],
                'user_caps': [],
                'total_usage': 0,
                'alerts': []
            }
            
            # Process global caps
            for cap in global_caps:
                usage_percentage = (cap.current_count / cap.cap_value) * 100 if cap.cap_value > 0 else 0
                
                cap_data['global_caps'].append({
                    'offer_id': cap.offer.id,
                    'offer_name': cap.offer.name,
                    'cap_type': cap.cap_type,
                    'cap_value': cap.cap_value,
                    'current_count': cap.current_count,
                    'usage_percentage': usage_percentage,
                    'status': 'warning' if usage_percentage >= 80 else 'normal'
                })
                
                cap_data['total_usage'] += cap.current_count
            
            # Process user caps
            for cap in user_caps:
                usage_percentage = (cap.shown_today / cap.max_shows_per_day) * 100 if cap.max_shows_per_day > 0 else 0
                
                cap_data['user_caps'].append({
                    'user_id': cap.user.id,
                    'username': cap.user.username,
                    'offer_id': cap.offer.id,
                    'offer_name': cap.offer.name,
                    'cap_type': cap.cap_type,
                    'max_shows_per_day': cap.max_shows_per_day,
                    'shown_today': cap.shown_today,
                    'usage_percentage': usage_percentage,
                    'status': 'warning' if usage_percentage >= 80 else 'normal'
                })
            
            return cap_data
            
        except Exception as e:
            logger.error(f"Error getting cap status: {e}")
            return {}
    
    @database_sync_to_async
    def check_cap_alerts(self, cap_data):
        """Check for cap alerts."""
        alerts = []
        
        try:
            # Check global cap alerts
            for cap in cap_data.get('global_caps', []):
                if cap['usage_percentage'] >= 90:
                    alerts.append({
                        'type': 'global_cap_warning',
                        'offer_id': cap['offer_id'],
                        'offer_name': cap['offer_name'],
                        'usage_percentage': cap['usage_percentage'],
                        'message': f"Global cap for {cap['offer_name']} is {cap['usage_percentage']:.1f}% used"
                    })
            
            # Check user cap alerts
            for cap in cap_data.get('user_caps', []):
                if cap['usage_percentage'] >= 90:
                    alerts.append({
                        'type': 'user_cap_warning',
                        'user_id': cap['user_id'],
                        'username': cap['username'],
                        'offer_id': cap['offer_id'],
                        'offer_name': cap['offer_name'],
                        'usage_percentage': cap['usage_percentage'],
                        'message': f"User {cap['username']} cap for {cap['offer_name']} is {cap['usage_percentage']:.1f}% used"
                    })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking cap alerts: {e}")
            return []


class RoutingDecisionConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time routing decisions.
    
    Streams live routing decisions as they happen,
    including scores, performance metrics, and user context.
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        try:
            user = self.scope["user"]
            
            if not user or not user.is_authenticated:
                await self.close(code=4001)
                return
            
            tenant_id = getattr(user, 'tenant_id', None)
            
            # Join routing decisions group
            group_name = f"routing_decisions_{tenant_id}"
            await self.channel_layer.group_add(
                group_name,
                self.channel_name
            )
            
            # Send recent decisions
            await self.send_recent_decisions(tenant_id)
            
            logger.info(f"Routing decisions WebSocket connected for tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Error in routing decisions connect: {e}")
            await self.close(code=4000)
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        try:
            user = self.scope["user"]
            tenant_id = getattr(user, 'tenant_id', None)
            
            # Leave routing decisions group
            group_name = f"routing_decisions_{tenant_id}"
            await self.channel_layer.group_discard(
                group_name,
                self.channel_name
            )
            
            logger.info(f"Routing decisions WebSocket disconnected for tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Error in routing decisions disconnect: {e}")
    
    async def send_recent_decisions(self, tenant_id):
        """Send recent routing decisions to client."""
        try:
            # Get last 50 decisions
            recent_decisions = await self.get_recent_decisions(tenant_id, limit=50)
            
            await self.send(text_data=json.dumps({
                'type': 'recent_decisions',
                'data': recent_decisions,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error sending recent decisions: {e}")
    
    @database_sync_to_async
    def get_recent_decisions(self, tenant_id, limit=50):
        """Get recent routing decisions."""
        try:
            decisions = RoutingDecisionLog.objects.filter(
                user__tenant_id=tenant_id
            ).select_related('user').order_by('-created_at')[:limit]
            
            return [
                {
                    'id': decision.id,
                    'user_id': decision.user.id,
                    'username': decision.user.username,
                    'offer_id': decision.offer_id,
                    'route_id': decision.route_id,
                    'score': decision.score,
                    'rank': decision.rank,
                    'response_time_ms': decision.response_time_ms,
                    'cache_hit': decision.cache_hit,
                    'personalization_applied': decision.personalization_applied,
                    'caps_checked': decision.caps_checked,
                    'fallback_used': decision.fallback_used,
                    'created_at': decision.created_at.isoformat()
                }
                for decision in decisions
            ]
            
        except Exception as e:
            logger.error(f"Error getting recent decisions: {e}")
            return []


class PerformanceMetricsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time performance metrics.
    
    Provides live performance data, response times,
    and system health metrics.
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        try:
            user = self.scope["user"]
            
            if not user or not user.is_authenticated:
                await self.close(code=4001)
                return
            
            tenant_id = getattr(user, 'tenant_id', None)
            
            # Join performance metrics group
            group_name = f"performance_metrics_{tenant_id}"
            await self.channel_layer.group_add(
                group_name,
                self.channel_name
            )
            
            # Send initial metrics
            await self.send_initial_metrics(tenant_id)
            
            # Start metrics streaming
            asyncio.create_task(self.start_metrics_streaming(tenant_id))
            
            logger.info(f"Performance metrics WebSocket connected for tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Error in performance metrics connect: {e}")
            await self.close(code=4000)
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        try:
            user = self.scope["user"]
            tenant_id = getattr(user, 'tenant_id', None)
            
            # Leave performance metrics group
            group_name = f"performance_metrics_{tenant_id}"
            await self.channel_layer.group_discard(
                group_name,
                self.channel_name
            )
            
            logger.info(f"Performance metrics WebSocket disconnected for tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Error in performance metrics disconnect: {e}")
    
    async def send_initial_metrics(self, tenant_id):
        """Send initial performance metrics."""
        try:
            metrics = await self.get_performance_metrics(tenant_id)
            
            await self.send(text_data=json.dumps({
                'type': 'initial_metrics',
                'data': metrics,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error sending initial metrics: {e}")
    
    async def start_metrics_streaming(self, tenant_id):
        """Start streaming performance metrics."""
        while True:
            try:
                # Get current metrics
                metrics = await self.get_performance_metrics(tenant_id)
                
                await self.send(text_data=json.dumps({
                    'type': 'metrics_update',
                    'data': metrics,
                    'timestamp': timezone.now().isoformat()
                }))
                
                # Wait 15 seconds for metrics updates
                await asyncio.sleep(15)
                
            except Exception as e:
                logger.error(f"Error in metrics streaming: {e}")
                await asyncio.sleep(15)
    
    @database_sync_to_async
    def get_performance_metrics(self, tenant_id):
        """Get current performance metrics."""
        try:
            # Get metrics from last 5 minutes
            five_minutes_ago = timezone.now() - timedelta(minutes=5)
            
            recent_decisions = RoutingDecisionLog.objects.filter(
                user__tenant_id=tenant_id,
                created_at__gte=five_minutes_ago
            )
            
            # Calculate metrics
            total_decisions = recent_decisions.count()
            avg_response_time = recent_decisions.aggregate(
                avg_response_time=models.Avg('response_time_ms')
            )['avg_response_time'] or 0
            
            cache_hit_rate = recent_decisions.filter(
                cache_hit=True
            ).count() / total_decisions * 100 if total_decisions > 0 else 0
            
            personalization_rate = recent_decisions.filter(
                personalization_applied=True
            ).count() / total_decisions * 100 if total_decisions > 0 else 0
            
            # Get system health
            system_health = monitoring_service.get_system_health()
            
            return {
                'total_decisions': total_decisions,
                'avg_response_time_ms': avg_response_time,
                'cache_hit_rate': cache_hit_rate,
                'personalization_rate': personalization_rate,
                'decisions_per_minute': total_decisions / 5,  # Last 5 minutes
                'system_health': system_health
            }
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {}


# Utility functions for WebSocket consumers
async def broadcast_to_tenant(tenant_id, message_type, data):
    """Broadcast message to all WebSocket connections for a tenant."""
    try:
        message = {
            'type': message_type,
            'data': data,
            'timestamp': timezone.now().isoformat()
        }
        
        # Send to all tenant groups
        groups = [
            f"routing_dashboard_{tenant_id}",
            f"cap_monitor_{tenant_id}",
            f"routing_decisions_{tenant_id}",
            f"performance_metrics_{tenant_id}"
        ]
        
        for group in groups:
            await channel_layer.group_send(
                group,
                {
                    'type': 'websocket.message',
                    'message': json.dumps(message)
                }
            )
    
    except Exception as e:
        logger.error(f"Error broadcasting to tenant {tenant_id}: {e}")


async def send_alert(tenant_id, alert_type, message, data=None):
    """Send alert to tenant WebSocket connections."""
    try:
        alert_message = {
            'type': 'alert',
            'alert_type': alert_type,
            'message': message,
            'data': data or {},
            'timestamp': timezone.now().isoformat()
        }
        
        await channel_layer.group_send(
            f"routing_dashboard_{tenant_id}",
            {
                'type': 'websocket.message',
                'message': json.dumps(alert_message)
            }
        )
    
    except Exception as e:
        logger.error(f"Error sending alert: {e}")


# Consumer registry
WEBSOCKET_CONSUMERS = {
    'routing_dashboard': RoutingDashboardConsumer,
    'cap_monitor': CapMonitorConsumer,
    'routing_decisions': RoutingDecisionConsumer,
    'performance_metrics': PerformanceMetricsConsumer,
}
