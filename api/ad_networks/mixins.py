"""
api/ad_networks/mixins.py
Mixins for ad networks module
SaaS-ready with tenant support
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from django.db import models
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.generic import View
from rest_framework import status
from rest_framework.response import Response

from .models import AdNetwork, Offer, UserOfferEngagement, OfferConversion, OfferReward
from .choices import OfferStatus, EngagementStatus, ConversionStatus, RewardStatus
from .constants import FRAUD_SCORE_THRESHOLD

logger = logging.getLogger(__name__)


class TenantMixin:
    """
    Mixin to handle tenant context
    """
    
    def get_tenant_id(self):
        """Get tenant ID from request"""
        # Try subdomain
        host = self.request.get_host()
        if host:
            subdomain = host.split('.')[0]
            if subdomain and subdomain != 'www':
                return subdomain
        
        # Try header
        tenant_id = self.request.META.get('HTTP_X_TENANT_ID')
        if tenant_id:
            return tenant_id
        
        # Try query parameter
        tenant_id = self.request.GET.get('tenant_id')
        if tenant_id:
            return tenant_id
        
        # Try session
        tenant_id = self.request.session.get('tenant_id')
        if tenant_id:
            return tenant_id
        
        # Default
        return 'default'
    
    def get_context_data(self, **kwargs):
        """Add tenant context to template"""
        context = super().get_context_data(**kwargs)
        context['tenant_id'] = self.get_tenant_id()
        return context
    
    def get_queryset(self):
        """Filter queryset by tenant"""
        queryset = super().get_queryset()
        tenant_id = self.get_tenant_id()
        
        if hasattr(queryset.model, 'tenant_id'):
            queryset = queryset.filter(tenant_id=tenant_id)
        
        return queryset


class SecurityMixin:
    """
    Mixin for security checks
    """
    
    def check_fraud_indicators(self, request, offer=None) -> Dict[str, Any]:
        """Check for fraud indicators"""
        fraud_score = 0
        indicators = []
        
        # Check IP address
        client_ip = self.get_client_ip(request)
        if self.is_suspicious_ip(client_ip):
            fraud_score += 40
            indicators.append('suspicious_ip')
        
        # Check user agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if self.is_bot_user_agent(user_agent):
            fraud_score += 30
            indicators.append('bot_user_agent')
        
        # Check request frequency
        if self.is_high_frequency_request(request):
            fraud_score += 25
            indicators.append('high_frequency')
        
        # Check offer-specific patterns
        if offer:
            if self.is_suspicious_offer_pattern(request, offer):
                fraud_score += 20
                indicators.append('suspicious_pattern')
        
        return {
            'fraud_score': min(fraud_score, 100),
            'indicators': indicators,
            'is_suspicious': fraud_score >= FRAUD_SCORE_THRESHOLD
        }
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        
        x_real_ip = request.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip
        
        return request.META.get('REMOTE_ADDR', '')
    
    def is_suspicious_ip(self, ip_address: str) -> bool:
        """Check if IP is suspicious"""
        try:
            from .models import KnownBadIP
            return KnownBadIP.objects.filter(
                ip_address=ip_address,
                is_active=True
            ).exists()
        except:
            return False
    
    def is_bot_user_agent(self, user_agent: str) -> bool:
        """Check if user agent indicates a bot"""
        bot_indicators = [
            'bot', 'crawler', 'spider', 'scraper', 'curl', 'wget',
            'python-requests', 'httpie', 'postman', 'insomnia'
        ]
        
        user_agent_lower = user_agent.lower()
        return any(indicator in user_agent_lower for indicator in bot_indicators)
    
    def is_high_frequency_request(self, request) -> bool:
        """Check if request frequency is too high"""
        client_ip = self.get_client_ip(request)
        cache_key = f"request_freq_{client_ip}"
        
        current_count = cache.get(cache_key, 0)
        if current_count > 100:  # More than 100 requests per minute
            return True
        
        cache.set(cache_key, current_count + 1, timeout=60)
        return False
    
    def is_suspicious_offer_pattern(self, request, offer) -> bool:
        """Check for suspicious offer patterns"""
        # Check if user is completing offers too quickly
        if request.user.is_authenticated:
            cache_key = f"user_offers_{request.user.id}"
            recent_offers = cache.get(cache_key, [])
            
            now = timezone.now()
            recent_offers = [t for t in recent_offers if now - t < timedelta(minutes=5)]
            
            if len(recent_offers) > 10:  # More than 10 offers in 5 minutes
                return True
            
            recent_offers.append(now)
            cache.set(cache_key, recent_offers, timeout=300)
        
        return False


class TrackingMixin:
    """
    Mixin for tracking user actions
    """
    
    def track_offer_click(self, offer, user=None):
        """Track offer click"""
        try:
            from .models import OfferClick
            
            click_data = {
                'offer': offer,
                'user': user,
                'ip_address': self.get_client_ip(self.request),
                'user_agent': self.request.META.get('HTTP_USER_AGENT', ''),
                'referrer_url': self.request.META.get('HTTP_REFERER', ''),
                'session_id': self.request.COOKIES.get('sessionid', ''),
                'tenant_id': self.get_tenant_id()
            }
            
            # Check fraud indicators
            fraud_check = self.check_fraud_indicators(self.request, offer)
            click_data.update(fraud_check)
            
            OfferClick.objects.create(**click_data)
            
            # Update offer click cache
            cache_key = f"offer_clicks_{offer.id}_{self.get_tenant_id()}"
            current_clicks = cache.get(cache_key, 0)
            cache.set(cache_key, current_clicks + 1, timeout=3600)
            
        except Exception as e:
            logger.error(f"Error tracking offer click: {str(e)}")
    
    def track_engagement(self, engagement):
        """Track user engagement"""
        try:
            # Update engagement cache
            cache_key = f"user_engagements_{engagement.user.id}_{self.get_tenant_id()}"
            cache.set(cache_key, engagement.id, timeout=3600)
            
            # Update offer engagement cache
            cache_key = f"offer_engagements_{engagement.offer.id}_{self.get_tenant_id()}"
            current_engagements = cache.get(cache_key, [])
            current_engagements.append(engagement.id)
            cache.set(cache_key, current_engagements[-100:], timeout=3600)  # Keep last 100
            
        except Exception as e:
            logger.error(f"Error tracking engagement: {str(e)}")
    
    def track_conversion(self, conversion):
        """Track conversion"""
        try:
            # Update conversion cache
            cache_key = f"user_conversions_{conversion.engagement.user.id}_{self.get_tenant_id()}"
            cache.set(cache_key, conversion.id, timeout=3600)
            
            # Update offer conversion cache
            cache_key = f"offer_conversions_{conversion.engagement.offer.id}_{self.get_tenant_id()}"
            current_conversions = cache.get(cache_key, [])
            current_conversions.append(conversion.id)
            cache.set(cache_key, current_conversions[-100:], timeout=3600)  # Keep last 100
            
        except Exception as e:
            logger.error(f"Error tracking conversion: {str(e)}")


class CacheMixin:
    """
    Mixin for caching operations
    """
    
    def get_cache_key(self, prefix: str, *args) -> str:
        """Generate cache key"""
        tenant_id = self.get_tenant_id()
        key_parts = [prefix, tenant_id] + [str(arg) for arg in args]
        return '_'.join(key_parts)
    
    def get_cached_data(self, key: str, timeout: int = 300):
        """Get data from cache"""
        return cache.get(key)
    
    def set_cached_data(self, key: str, data, timeout: int = 300):
        """Set data in cache"""
        cache.set(key, data, timeout)
    
    def delete_cached_data(self, key: str):
        """Delete data from cache"""
        cache.delete(key)
    
    def clear_cache_pattern(self, pattern: str):
        """Clear cache keys matching pattern"""
        # This would use your cache backend's pattern matching
        # For now, just log
        logger.info(f"Clearing cache pattern: {pattern}")


class ValidationMixin:
    """
    Mixin for validation operations
    """
    
    def validate_offer_access(self, offer, user=None) -> Dict[str, Any]:
        """Validate if user can access offer"""
        result = {
            'valid': True,
            'errors': []
        }
        
        # Check if offer is active
        if offer.status != OfferStatus.ACTIVE:
            result['valid'] = False
            result['errors'].append('Offer is not active')
        
        # Check if offer is expired
        if offer.expires_at and offer.expires_at < timezone.now():
            result['valid'] = False
            result['errors'].append('Offer has expired')
        
        # Check user authentication
        if not user or not user.is_authenticated:
            result['valid'] = False
            result['errors'].append('User authentication required')
        
        # Check daily limit
        if user and user.is_authenticated:
            if self.check_daily_limit(user, offer):
                result['valid'] = False
                result['errors'].append('Daily limit exceeded')
        
        return result
    
    def check_daily_limit(self, user, offer) -> bool:
        """Check if user has exceeded daily limit for offer"""
        try:
            from .models import OfferDailyLimit
            
            today = timezone.now().date()
            daily_limit = OfferDailyLimit.objects.filter(
                user=user,
                offer=offer,
                tenant_id=self.get_tenant_id()
            ).first()
            
            if daily_limit:
                if daily_limit.last_reset_at.date() < today:
                    # Reset daily count
                    daily_limit.count_today = 0
                    daily_limit.last_reset_at = timezone.now()
                    daily_limit.save()
                
                return daily_limit.count_today >= daily_limit.daily_limit
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking daily limit: {str(e)}")
            return False


class NotificationMixin:
    """
    Mixin for sending notifications
    """
    
    def send_notification(self, user, title: str, message: str, 
                         notification_type: str = 'info', 
                         data: Dict[str, Any] = None):
        """Send notification to user"""
        try:
            # This would integrate with your notification system
            # For now, just log
            logger.info(f"Notification to {user.username}: {title} - {message}")
            
            # Add to user's notification cache
            cache_key = f"user_notifications_{user.id}_{self.get_tenant_id()}"
            notifications = cache.get(cache_key, [])
            
            notification = {
                'title': title,
                'message': message,
                'type': notification_type,
                'data': data or {},
                'timestamp': timezone.now().isoformat()
            }
            
            notifications.append(notification)
            cache.set(cache_key, notifications[-50:], timeout=86400)  # Keep last 50
            
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
    
    def send_conversion_notification(self, conversion):
        """Send conversion notification"""
        user = conversion.engagement.user
        
        if conversion.conversion_status == ConversionStatus.APPROVED:
            self.send_notification(
                user,
                'Conversion Approved!',
                f'Your conversion for {conversion.engagement.offer.title} has been approved.',
                'success',
                {
                    'conversion_id': conversion.id,
                    'offer_id': conversion.engagement.offer.id,
                    'payout': float(conversion.payout)
                }
            )
        elif conversion.conversion_status == ConversionStatus.REJECTED:
            self.send_notification(
                user,
                'Conversion Rejected',
                f'Your conversion for {conversion.engagement.offer.title} has been rejected.',
                'error',
                {
                    'conversion_id': conversion.id,
                    'offer_id': conversion.engagement.offer.id,
                    'reason': conversion.rejection_reason
                }
            )
    
    def send_reward_notification(self, reward):
        """Send reward notification"""
        user = reward.user
        
        if reward.status == RewardStatus.APPROVED:
            self.send_notification(
                user,
                'Reward Approved!',
                f'Your reward of {reward.amount} {reward.currency} has been approved.',
                'success',
                {
                    'reward_id': reward.id,
                    'amount': float(reward.amount),
                    'currency': reward.currency
                }
            )
        elif reward.status == RewardStatus.PAID:
            self.send_notification(
                user,
                'Reward Paid!',
                f'Your reward of {reward.amount} {reward.currency} has been paid.',
                'success',
                {
                    'reward_id': reward.id,
                    'amount': float(reward.amount),
                    'currency': reward.currency,
                    'payment_reference': reward.payment_reference
                }
            )


class AnalyticsMixin:
    """
    Mixin for analytics operations
    """
    
    def track_event(self, event_type: str, data: Dict[str, Any]):
        """Track analytics event"""
        try:
            # This would integrate with your analytics system
            # For now, just log
            logger.info(f"Analytics event {event_type}: {data}")
            
            # Add to analytics cache
            cache_key = f"analytics_{event_type}_{self.get_tenant_id()}"
            events = cache.get(cache_key, [])
            
            event = {
                'type': event_type,
                'data': data,
                'timestamp': timezone.now().isoformat()
            }
            
            events.append(event)
            cache.set(cache_key, events[-1000:], timeout=3600)  # Keep last 1000
            
        except Exception as e:
            logger.error(f"Error tracking analytics event: {str(e)}")
    
    def track_offer_event(self, event_type: str, offer, user=None):
        """Track offer-specific event"""
        data = {
            'offer_id': offer.id,
            'offer_title': offer.title,
            'network_id': offer.ad_network.id,
            'network_name': offer.ad_network.name
        }
        
        if user:
            data['user_id'] = user.id
            data['user_username'] = user.username
        
        self.track_event(event_type, data)
    
    def track_user_event(self, event_type: str, user, additional_data: Dict[str, Any] = None):
        """Track user-specific event"""
        data = {
            'user_id': user.id,
            'user_username': user.username,
            'ip_address': self.get_client_ip(self.request),
            'user_agent': self.request.META.get('HTTP_USER_AGENT', '')
        }
        
        if additional_data:
            data.update(additional_data)
        
        self.track_event(event_type, data)


class RateLimitMixin:
    """
    Mixin for rate limiting
    """
    
    def check_rate_limit(self, key: str, limit: int, window: int = 60) -> bool:
        """Check if rate limit is exceeded"""
        cache_key = f"rate_limit_{key}_{self.get_tenant_id()}"
        current_count = cache.get(cache_key, 0)
        
        if current_count >= limit:
            return False
        
        cache.set(cache_key, current_count + 1, timeout=window)
        return True
    
    def get_rate_limit_key(self, prefix: str) -> str:
        """Generate rate limit key"""
        if self.request.user.is_authenticated:
            return f"{prefix}_user_{self.request.user.id}"
        else:
            return f"{prefix}_ip_{self.get_client_ip(self.request)}"


class APIResponseMixin:
    """
    Mixin for standardized API responses
    """
    
    def success_response(self, data: Any = None, message: str = None, 
                        status_code: int = status.HTTP_200_OK) -> Response:
        """Return success response"""
        response_data = {
            'success': True,
            'message': message or 'Success',
            'data': data
        }
        return Response(response_data, status=status_code)
    
    def error_response(self, message: str, errors: List[str] = None,
                      status_code: int = status.HTTP_400_BAD_REQUEST) -> Response:
        """Return error response"""
        response_data = {
            'success': False,
            'message': message,
            'errors': errors or []
        }
        return Response(response_data, status=status_code)
    
    def validation_error_response(self, errors: Dict[str, List[str]]) -> Response:
        """Return validation error response"""
        response_data = {
            'success': False,
            'message': 'Validation failed',
            'errors': errors
        }
        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)


class WebSocketMixin:
    """
    Mixin for WebSocket operations
    """
    
    def send_websocket_message(self, channel: str, message: Dict[str, Any]):
        """Send message via WebSocket"""
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                channel,
                {
                    'type': 'broadcast_message',
                    'message': message
                }
            )
            
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {str(e)}")
    
    def send_offer_update(self, offer, update_type: str):
        """Send offer update via WebSocket"""
        channel = f"offers_{self.get_tenant_id()}"
        
        message = {
            'type': 'offer_update',
            'update_type': update_type,
            'offer_id': offer.id,
            'offer_data': {
                'id': offer.id,
                'title': offer.title,
                'status': offer.status,
                'reward_amount': float(offer.reward_amount)
            },
            'timestamp': timezone.now().isoformat()
        }
        
        self.send_websocket_message(channel, message)
    
    def send_conversion_update(self, conversion, update_type: str):
        """Send conversion update via WebSocket"""
        channel = f"conversions_{self.get_tenant_id()}"
        
        message = {
            'type': 'conversion_update',
            'update_type': update_type,
            'conversion_id': conversion.id,
            'user_id': conversion.engagement.user.id,
            'offer_id': conversion.engagement.offer.id,
            'status': conversion.conversion_status,
            'payout': float(conversion.payout),
            'timestamp': timezone.now().isoformat()
        }
        
        self.send_websocket_message(channel, message)


class ExportMixin:
    """
    Mixin for data export operations
    """
    
    def generate_export_filename(self, export_type: str, format: str) -> str:
        """Generate export filename"""
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        tenant_id = self.get_tenant_id()
        return f"{export_type}_{tenant_id}_{timestamp}.{format}"
    
    def export_to_csv(self, queryset, fields: List[str], filename: str):
        """Export queryset to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow(fields)
        
        for obj in queryset:
            row = []
            for field in fields:
                value = getattr(obj, field, '')
                if hasattr(value, 'isoformat'):  # Datetime
                    value = value.isoformat()
                elif isinstance(value, (int, float)):
                    value = str(value)
                row.append(value)
            writer.writerow(row)
        
        return response
    
    def export_to_json(self, queryset, filename: str):
        """Export queryset to JSON"""
        from django.http import HttpResponse
        import json
        
        data = []
        for obj in queryset:
            item = {}
            for field in obj._meta.fields:
                value = getattr(obj, field.name, '')
                if hasattr(value, 'isoformat'):  # Datetime
                    value = value.isoformat()
                elif isinstance(value, (int, float, str)):
                    value = value
                else:
                    value = str(value)
                item[field.name] = value
            data.append(item)
        
        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write(json.dumps(data, indent=2))
        
        return response


# Combined mixins for common use cases
class AdNetworkViewMixin(TenantMixin, SecurityMixin, TrackingMixin, 
                         CacheMixin, ValidationMixin, NotificationMixin,
                         AnalyticsMixin, RateLimitMixin, APIResponseMixin):
    """
    Combined mixin for ad network views
    """
    pass


class OfferViewMixin(TenantMixin, SecurityMixin, TrackingMixin, 
                    CacheMixin, ValidationMixin, NotificationMixin,
                    AnalyticsMixin, WebSocketMixin):
    """
    Combined mixin for offer views
    """
    pass


class ConversionViewMixin(TenantMixin, SecurityMixin, TrackingMixin, 
                         ValidationMixin, NotificationMixin, AnalyticsMixin,
                         WebSocketMixin):
    """
    Combined mixin for conversion views
    """
    pass


class RewardViewMixin(TenantMixin, SecurityMixin, TrackingMixin, 
                      ValidationMixin, NotificationMixin, AnalyticsMixin):
    """
    Combined mixin for reward views
    """
    pass


class AdminViewMixin(TenantMixin, SecurityMixin, CacheMixin, 
                     AnalyticsMixin, ExportMixin, APIResponseMixin):
    """
    Combined mixin for admin views
    """
    pass


# Export all mixins
__all__ = [
    # Base mixins
    'TenantMixin',
    'SecurityMixin',
    'TrackingMixin',
    'CacheMixin',
    'ValidationMixin',
    'NotificationMixin',
    'AnalyticsMixin',
    'RateLimitMixin',
    'APIResponseMixin',
    'WebSocketMixin',
    'ExportMixin',
    
    # Combined mixins
    'AdNetworkViewMixin',
    'OfferViewMixin',
    'ConversionViewMixin',
    'RewardViewMixin',
    'AdminViewMixin'
]
