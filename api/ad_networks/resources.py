"""
api/ad_networks/resources.py
Resource classes for ad networks module
SaaS-ready with tenant support
"""

import logging
import json
import csv
import io
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, BinaryIO
from enum import Enum

from django.http import HttpResponse, JsonResponse
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from django.contrib.auth import get_user_model

from .models import (
    AdNetwork, Offer, OfferCategory, UserOfferEngagement,
    OfferConversion, OfferReward, UserWallet, OfferClick,
    NetworkHealthCheck, OfferDailyLimit, OfferTag, OfferTagging
)
from .choices import OfferStatus, EngagementStatus, ConversionStatus, RewardStatus
from .constants import CACHE_TIMEOUTS

logger = logging.getLogger(__name__)
User = get_user_model()


class ResourceType(Enum):
    """Resource types"""
    
    OFFER = "offer"
    CONVERSION = "conversion"
    REWARD = "reward"
    USER = "user"
    NETWORK = "network"
    ANALYTICS = "analytics"
    REPORT = "report"
    EXPORT = "export"


class FormatType(Enum):
    """Export format types"""
    
    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"
    XML = "xml"


class BaseResource:
    """Base resource class"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.cache_timeout = CACHE_TIMEOUTS.get('default', 300)
    
    def get_cache_key(self, resource_type: str, identifier: str = '') -> str:
        """Generate cache key"""
        key_parts = ['ad_networks_resource', resource_type, self.tenant_id]
        if identifier:
            key_parts.append(identifier)
        return '_'.join(key_parts)
    
    def get_from_cache(self, cache_key: str) -> Any:
        """Get data from cache"""
        return cache.get(cache_key)
    
    def set_cache(self, cache_key: str, data: Any, timeout: int = None):
        """Set data in cache"""
        timeout = timeout or self.cache_timeout
        cache.set(cache_key, data, timeout)
    
    def delete_cache(self, cache_key: str):
        """Delete cache entry"""
        cache.delete(cache_key)
    
    def clear_cache_pattern(self, pattern: str):
        """Clear cache entries matching pattern"""
        # This would use cache backend's pattern matching
        # For now, just log
        logger.info(f"Clearing cache pattern: {pattern}")


class OfferResource(BaseResource):
    """Resource for offers"""
    
    def get_offer_list(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get list of offers"""
        cache_key = self.get_cache_key('offer_list', str(hash(frozenset(filters.items() if filters else []))))
        cached_data = self.get_from_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        queryset = Offer.objects.filter(tenant_id=self.tenant_id)
        
        if filters:
            if 'status' in filters:
                queryset = queryset.filter(status=filters['status'])
            
            if 'category_id' in filters:
                queryset = queryset.filter(category_id=filters['category_id'])
            
            if 'network_id' in filters:
                queryset = queryset.filter(ad_network_id=filters['network_id'])
            
            if 'min_reward' in filters:
                queryset = queryset.filter(reward_amount__gte=filters['min_reward'])
            
            if 'max_reward' in filters:
                queryset = queryset.filter(reward_amount__lte=filters['max_reward'])
            
            if 'countries' in filters:
                queryset = queryset.filter(countries__contains=filters['countries'])
            
            if 'platforms' in filters:
                queryset = queryset.filter(platforms__contains=filters['platforms'])
            
            if 'device_type' in filters:
                queryset = queryset.filter(device_type=filters['device_type'])
            
            if 'difficulty' in filters:
                queryset = queryset.filter(difficulty=filters['difficulty'])
            
            if 'is_featured' in filters:
                queryset = queryset.filter(is_featured=filters['is_featured'])
            
            if 'is_hot' in filters:
                queryset = queryset.filter(is_hot=filters['is_hot'])
            
            if 'is_new' in filters:
                queryset = queryset.filter(is_new=filters['is_new'])
        
        # Order by priority and creation date
        queryset = queryset.order_by('-priority', '-created_at')
        
        # Serialize data
        offers_data = []
        for offer in queryset.select_related('ad_network', 'category'):
            offers_data.append({
                'id': offer.id,
                'external_id': offer.external_id,
                'title': offer.title,
                'description': offer.description,
                'short_description': offer.short_description,
                'reward_amount': float(offer.reward_amount),
                'currency': offer.reward_currency,
                'network': {
                    'id': offer.ad_network.id,
                    'name': offer.ad_network.name,
                    'type': offer.ad_network.network_type
                },
                'category': {
                    'id': offer.category.id if offer.category else None,
                    'name': offer.category.name if offer.category else None
                },
                'status': offer.status,
                'countries': offer.countries,
                'platforms': offer.platforms,
                'device_type': offer.device_type,
                'difficulty': offer.difficulty,
                'estimated_time': offer.estimated_time,
                'requirements': offer.requirements,
                'instructions': offer.instructions,
                'preview_url': offer.preview_url,
                'tracking_url': offer.tracking_url,
                'is_featured': offer.is_featured,
                'is_hot': offer.is_hot,
                'is_new': offer.is_new,
                'priority': offer.priority,
                'expires_at': offer.expires_at.isoformat() if offer.expires_at else None,
                'created_at': offer.created_at.isoformat(),
                'updated_at': offer.updated_at.isoformat()
            })
        
        # Cache the result
        self.set_cache(cache_key, offers_data)
        
        return offers_data
    
    def get_offer_details(self, offer_id: int) -> Optional[Dict[str, Any]]:
        """Get offer details"""
        cache_key = self.get_cache_key('offer_details', str(offer_id))
        cached_data = self.get_from_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        try:
            offer = Offer.objects.get(
                id=offer_id,
                tenant_id=self.tenant_id
            )
            
            # Get additional stats
            click_stats = OfferClick.objects.filter(
                offer=offer,
                tenant_id=self.tenant_id
            ).aggregate(
                total_clicks=Count('id'),
                unique_clicks=Count('ip_address', distinct=True)
            )
            
            engagement_stats = UserOfferEngagement.objects.filter(
                offer=offer,
                tenant_id=self.tenant_id
            ).aggregate(
                total_engagements=Count('id'),
                completed_engagements=Count(
                    'id',
                    filter=Q(status=EngagementStatus.COMPLETED)
                )
            )
            
            conversion_stats = OfferConversion.objects.filter(
                engagement__offer=offer,
                tenant_id=self.tenant_id
            ).aggregate(
                total_conversions=Count('id'),
                approved_conversions=Count(
                    'id',
                    filter=Q(conversion_status=ConversionStatus.APPROVED)
                ),
                total_payout=Sum('payout')
            )
            
            offer_data = {
                'id': offer.id,
                'external_id': offer.external_id,
                'title': offer.title,
                'description': offer.description,
                'short_description': offer.short_description,
                'reward_amount': float(offer.reward_amount),
                'currency': offer.reward_currency,
                'network': {
                    'id': offer.ad_network.id,
                    'name': offer.ad_network.name,
                    'type': offer.ad_network.network_type,
                    'category': offer.ad_network.category
                },
                'category': {
                    'id': offer.category.id if offer.category else None,
                    'name': offer.category.name if offer.category else None
                },
                'status': offer.status,
                'countries': offer.countries,
                'platforms': offer.platforms,
                'device_type': offer.device_type,
                'difficulty': offer.difficulty,
                'estimated_time': offer.estimated_time,
                'requirements': offer.requirements,
                'instructions': offer.instructions,
                'preview_url': offer.preview_url,
                'tracking_url': offer.tracking_url,
                'is_featured': offer.is_featured,
                'is_hot': offer.is_hot,
                'is_new': offer.is_new,
                'priority': offer.priority,
                'expires_at': offer.expires_at.isoformat() if offer.expires_at else None,
                'created_at': offer.created_at.isoformat(),
                'updated_at': offer.updated_at.isoformat(),
                'stats': {
                    'clicks': click_stats,
                    'engagements': engagement_stats,
                    'conversions': conversion_stats
                }
            }
            
            # Cache the result
            self.set_cache(cache_key, offer_data)
            
            return offer_data
            
        except Offer.DoesNotExist:
            return None
    
    def get_featured_offers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get featured offers"""
        cache_key = self.get_cache_key('featured_offers', str(limit))
        cached_data = self.get_from_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        offers = Offer.objects.filter(
            tenant_id=self.tenant_id,
            is_featured=True,
            status=OfferStatus.ACTIVE
        ).order_by('-priority', '-created_at')[:limit]
        
        offers_data = []
        for offer in offers.select_related('ad_network', 'category'):
            offers_data.append({
                'id': offer.id,
                'title': offer.title,
                'description': offer.description,
                'reward_amount': float(offer.reward_amount),
                'currency': offer.reward_currency,
                'network': offer.ad_network.name,
                'category': offer.category.name if offer.category else None,
                'difficulty': offer.difficulty,
                'estimated_time': offer.estimated_time,
                'preview_url': offer.preview_url,
                'tracking_url': offer.tracking_url
            })
        
        # Cache the result
        self.set_cache(cache_key, offers_data)
        
        return offers_data
    
    def get_hot_offers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get hot offers"""
        cache_key = self.get_cache_key('hot_offers', str(limit))
        cached_data = self.get_from_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        offers = Offer.objects.filter(
            tenant_id=self.tenant_id,
            is_hot=True,
            status=OfferStatus.ACTIVE
        ).order_by('-priority', '-created_at')[:limit]
        
        offers_data = []
        for offer in offers.select_related('ad_network', 'category'):
            offers_data.append({
                'id': offer.id,
                'title': offer.title,
                'description': offer.description,
                'reward_amount': float(offer.reward_amount),
                'currency': offer.reward_currency,
                'network': offer.ad_network.name,
                'category': offer.category.name if offer.category else None,
                'difficulty': offer.difficulty,
                'estimated_time': offer.estimated_time,
                'preview_url': offer.preview_url,
                'tracking_url': offer.tracking_url
            })
        
        # Cache the result
        self.set_cache(cache_key, offers_data)
        
        return offers_data


class UserResource(BaseResource):
    """Resource for user data"""
    
    def get_user_stats(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user statistics"""
        cache_key = self.get_cache_key('user_stats', str(user_id))
        cached_data = self.get_from_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        try:
            user = User.objects.get(id=user_id)
            
            # Get engagement stats
            engagement_stats = UserOfferEngagement.objects.filter(
                user=user,
                tenant_id=self.tenant_id
            ).aggregate(
                total_engagements=Count('id'),
                completed_engagements=Count(
                    'id',
                    filter=Q(status=EngagementStatus.COMPLETED)
                )
            )
            
            # Get conversion stats
            conversion_stats = OfferConversion.objects.filter(
                engagement__user=user,
                tenant_id=self.tenant_id
            ).aggregate(
                total_conversions=Count('id'),
                approved_conversions=Count(
                    'id',
                    filter=Q(conversion_status=ConversionStatus.APPROVED)
                ),
                total_payout=Sum('payout')
            )
            
            # Get reward stats
            reward_stats = OfferReward.objects.filter(
                user=user,
                tenant_id=self.tenant_id
            ).aggregate(
                total_rewards=Count('id'),
                approved_rewards=Count(
                    'id',
                    filter=Q(status=RewardStatus.APPROVED)
                ),
                total_earned=Sum('amount')
            )
            
            # Get wallet info
            try:
                wallet = UserWallet.objects.get(
                    user=user,
                    tenant_id=self.tenant_id
                )
                wallet_balance = float(wallet.balance)
                total_earned = float(wallet.total_earned)
            except UserWallet.DoesNotExist:
                wallet_balance = 0.0
                total_earned = 0.0
            
            user_stats = {
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'engagements': engagement_stats,
                'conversions': conversion_stats,
                'rewards': reward_stats,
                'wallet': {
                    'balance': wallet_balance,
                    'total_earned': total_earned
                }
            }
            
            # Cache the result
            self.set_cache(cache_key, user_stats, timeout=600)  # 10 minutes
            
            return user_stats
            
        except User.DoesNotExist:
            return None
    
    def get_user_activity(self, user_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """Get user activity"""
        cache_key = self.get_cache_key('user_activity', f"{user_id}_{days}")
        cached_data = self.get_from_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get recent activities
        activities = []
        
        # Engagements
        engagements = UserOfferEngagement.objects.filter(
            user_id=user_id,
            tenant_id=self.tenant_id,
            created_at__gte=cutoff_date
        ).order_by('-created_at')[:20]
        
        for engagement in engagements.select_related('offer'):
            activities.append({
                'type': 'engagement',
                'id': engagement.id,
                'offer_title': engagement.offer.title,
                'status': engagement.status,
                'created_at': engagement.created_at.isoformat(),
                'completed_at': engagement.completed_at.isoformat() if engagement.completed_at else None
            })
        
        # Conversions
        conversions = OfferConversion.objects.filter(
            engagement__user_id=user_id,
            tenant_id=self.tenant_id,
            created_at__gte=cutoff_date
        ).order_by('-created_at')[:20]
        
        for conversion in conversions.select_related('engagement__offer'):
            activities.append({
                'type': 'conversion',
                'id': conversion.id,
                'offer_title': conversion.engagement.offer.title,
                'payout': float(conversion.payout),
                'currency': conversion.currency,
                'status': conversion.conversion_status,
                'created_at': conversion.created_at.isoformat(),
                'approved_at': conversion.approved_at.isoformat() if conversion.approved_at else None
            })
        
        # Sort by date
        activities.sort(key=lambda x: x['created_at'], reverse=True)
        
        # Cache the result
        self.set_cache(cache_key, activities, timeout=300)  # 5 minutes
        
        return activities


class AnalyticsResource(BaseResource):
    """Resource for analytics data"""
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get dashboard statistics"""
        cache_key = self.get_cache_key('dashboard_stats')
        cached_data = self.get_from_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        # Overall stats
        total_offers = Offer.objects.filter(
            tenant_id=self.tenant_id,
            status=OfferStatus.ACTIVE
        ).count()
        
        total_networks = AdNetwork.objects.filter(
            tenant_id=self.tenant_id,
            is_active=True
        ).count()
        
        # Last 30 days stats
        cutoff_date = timezone.now() - timedelta(days=30)
        
        total_conversions = OfferConversion.objects.filter(
            engagement__tenant_id=self.tenant_id,
            created_at__gte=cutoff_date
        ).count()
        
        total_payout = OfferConversion.objects.filter(
            engagement__tenant_id=self.tenant_id,
            conversion_status=ConversionStatus.APPROVED,
            created_at__gte=cutoff_date
        ).aggregate(
            total=Sum('payout')
        )['total'] or 0
        
        total_users = User.objects.filter(
            userofferengagement__tenant_id=self.tenant_id,
            userofferengagement__created_at__gte=cutoff_date
        ).distinct().count()
        
        dashboard_stats = {
            'offers': {
                'total_active': total_offers
            },
            'networks': {
                'total_active': total_networks
            },
            'conversions': {
                'last_30_days': total_conversions,
                'total_payout': float(total_payout)
            },
            'users': {
                'last_30_days': total_users
            },
            'generated_at': timezone.now().isoformat()
        }
        
        # Cache the result
        self.set_cache(cache_key, dashboard_stats, timeout=600)  # 10 minutes
        
        return dashboard_stats
    
    def get_offer_analytics(self, offer_id: int, days: int = 30) -> Optional[Dict[str, Any]]:
        """Get offer analytics"""
        cache_key = self.get_cache_key('offer_analytics', f"{offer_id}_{days}")
        cached_data = self.get_from_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        try:
            offer = Offer.objects.get(
                id=offer_id,
                tenant_id=self.tenant_id
            )
            
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Click analytics
            clicks = OfferClick.objects.filter(
                offer=offer,
                tenant_id=self.tenant_id,
                clicked_at__gte=cutoff_date
            )
            
            click_stats = clicks.aggregate(
                total_clicks=Count('id'),
                unique_clicks=Count('ip_address', distinct=True)
            )
            
            # Engagement analytics
            engagements = UserOfferEngagement.objects.filter(
                offer=offer,
                tenant_id=self.tenant_id,
                created_at__gte=cutoff_date
            )
            
            engagement_stats = engagements.aggregate(
                total_engagements=Count('id'),
                completed_engagements=Count(
                    'id',
                    filter=Q(status=EngagementStatus.COMPLETED)
                )
            )
            
            # Conversion analytics
            conversions = OfferConversion.objects.filter(
                engagement__offer=offer,
                tenant_id=self.tenant_id,
                created_at__gte=cutoff_date
            )
            
            conversion_stats = conversions.aggregate(
                total_conversions=Count('id'),
                approved_conversions=Count(
                    'id',
                    filter=Q(conversion_status=ConversionStatus.APPROVED)
                ),
                total_payout=Sum('payout'),
                avg_payout=Avg('payout')
            )
            
            # Top countries
            top_countries = clicks.values('country').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            # Top devices
            top_devices = clicks.values('device').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            analytics_data = {
                'offer_id': offer.id,
                'offer_title': offer.title,
                'period_days': days,
                'clicks': click_stats,
                'engagements': engagement_stats,
                'conversions': conversion_stats,
                'top_countries': list(top_countries),
                'top_devices': list(top_devices),
                'generated_at': timezone.now().isoformat()
            }
            
            # Cache the result
            self.set_cache(cache_key, analytics_data, timeout=300)  # 5 minutes
            
            return analytics_data
            
        except Offer.DoesNotExist:
            return None


class ExportResource(BaseResource):
    """Resource for data export"""
    
    def export_offers(self, format_type: str = 'json', 
                      filters: Dict[str, Any] = None) -> Union[str, bytes]:
        """Export offers data"""
        offers_data = OfferResource(self.tenant_id).get_offer_list(filters)
        
        if format_type == FormatType.JSON.value:
            return self._export_json(offers_data)
        elif format_type == FormatType.CSV.value:
            return self._export_csv(offers_data, 'offers')
        elif format_type == FormatType.EXCEL.value:
            return self._export_excel(offers_data, 'offers')
        else:
            raise ValueError(f"Unsupported format: {format_type}")
    
    def export_conversions(self, format_type: str = 'json',
                         filters: Dict[str, Any] = None) -> Union[str, bytes]:
        """Export conversions data"""
        # Get conversions data
        queryset = OfferConversion.objects.filter(tenant_id=self.tenant_id)
        
        if filters:
            if 'date_from' in filters:
                queryset = queryset.filter(created_at__gte=filters['date_from'])
            
            if 'date_to' in filters:
                queryset = queryset.filter(created_at__lte=filters['date_to'])
            
            if 'status' in filters:
                queryset = queryset.filter(conversion_status=filters['status'])
            
            if 'user_id' in filters:
                queryset = queryset.filter(engagement__user_id=filters['user_id'])
            
            if 'offer_id' in filters:
                queryset = queryset.filter(engagement__offer_id=filters['offer_id'])
        
        conversions_data = []
        for conversion in queryset.select_related('engagement__user', 'engagement__offer'):
            conversions_data.append({
                'id': conversion.id,
                'user_id': conversion.engagement.user.id,
                'username': conversion.engagement.user.username,
                'offer_id': conversion.engagement.offer.id,
                'offer_title': conversion.engagement.offer.title,
                'payout': float(conversion.payout),
                'currency': conversion.currency,
                'status': conversion.conversion_status,
                'fraud_score': conversion.fraud_score,
                'created_at': conversion.created_at.isoformat(),
                'approved_at': conversion.approved_at.isoformat() if conversion.approved_at else None,
                'rejected_at': conversion.rejected_at.isoformat() if conversion.rejected_at else None
            })
        
        if format_type == FormatType.JSON.value:
            return self._export_json(conversions_data)
        elif format_type == FormatType.CSV.value:
            return self._export_csv(conversions_data, 'conversions')
        elif format_type == FormatType.EXCEL.value:
            return self._export_excel(conversions_data, 'conversions')
        else:
            raise ValueError(f"Unsupported format: {format_type}")
    
    def _export_json(self, data: List[Dict[str, Any]]) -> str:
        """Export data as JSON"""
        return json.dumps({
            'success': True,
            'data': data,
            'total_count': len(data),
            'exported_at': timezone.now().isoformat()
        }, indent=2)
    
    def _export_csv(self, data: List[Dict[str, Any]], resource_type: str) -> bytes:
        """Export data as CSV"""
        if not data:
            return b''
        
        output = io.StringIO()
        
        if data:
            # Get headers from first item
            headers = list(data[0].keys())
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            
            # Write data rows
            for item in data:
                # Flatten nested objects
                flattened_item = {}
                for key, value in item.items():
                    if isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            flattened_item[f"{key}_{sub_key}"] = sub_value
                    else:
                        flattened_item[key] = value
                
                writer.writerow(flattened_item)
        
        return output.getvalue().encode('utf-8')
    
    def _export_excel(self, data: List[Dict[str, Any]], resource_type: str) -> bytes:
        """Export data as Excel (CSV fallback)"""
        # For now, return CSV format
        # In production, this would use a library like openpyxl
        return self._export_csv(data, resource_type)


# Resource manager
class ResourceManager:
    """Manager for all resources"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.offer_resource = OfferResource(tenant_id)
        self.user_resource = UserResource(tenant_id)
        self.analytics_resource = AnalyticsResource(tenant_id)
        self.export_resource = ExportResource(tenant_id)
    
    def get_resource(self, resource_type: ResourceType):
        """Get resource by type"""
        if resource_type == ResourceType.OFFER:
            return self.offer_resource
        elif resource_type == ResourceType.USER:
            return self.user_resource
        elif resource_type == ResourceType.ANALYTICS:
            return self.analytics_resource
        elif resource_type == ResourceType.EXPORT:
            return self.export_resource
        else:
            raise ValueError(f"Unknown resource type: {resource_type}")
    
    def clear_cache(self, resource_type: ResourceType = None):
        """Clear cache for specific or all resources"""
        if resource_type:
            resource = self.get_resource(resource_type)
            resource.clear_cache_pattern(f"{resource_type.value}_*")
        else:
            # Clear all resource caches
            for rt in ResourceType:
                resource = self.get_resource(rt)
                resource.clear_cache_pattern(f"{rt.value}_*")


# Export all classes
__all__ = [
    # Enums
    'ResourceType',
    'FormatType',
    
    # Base classes
    'BaseResource',
    'OfferResource',
    'UserResource',
    'AnalyticsResource',
    'ExportResource',
    
    # Manager
    'ResourceManager'
]
