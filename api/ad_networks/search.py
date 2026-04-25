"""
api/ad_networks/search.py
Search functionality for ad networks module
SaaS-ready with tenant support
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, Tuple
from django.db.models import Q, Count, Sum, Avg, F, ExpressionWrapper, FloatField
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction

from .models import (
    AdNetwork, Offer, OfferCategory, UserOfferEngagement,
    OfferConversion, OfferReward, OfferTag, OfferTagging,
    OfferClick, NetworkAPILog, UserWallet
)
from .choices import (
    OfferStatus, EngagementStatus, ConversionStatus,
    RewardStatus, NetworkStatus, DeviceType, Difficulty
)
from .constants import FRAUD_SCORE_THRESHOLD, CACHE_TIMEOUTS
from .helpers import get_cache_key, calculate_percentage

logger = logging.getLogger(__name__)
User = get_user_model()


class OfferSearchEngine:
    """Advanced search engine for offers"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.cache_timeout = CACHE_TIMEOUTS.get('offer_search', 300)
    
    def search_offers(self, query: str = None, filters: Dict = None, 
                     sort_by: str = 'created_at', order: str = 'desc',
                     page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """
        Search offers with advanced filtering and sorting
        """
        # Build base queryset
        queryset = Offer.objects.filter(
            tenant_id=self.tenant_id,
            status=OfferStatus.ACTIVE
        )
        
        # Apply text search
        if query:
            queryset = self._apply_text_search(queryset, query)
        
        # Apply filters
        if filters:
            queryset = self._apply_filters(queryset, filters)
        
        # Apply sorting
        queryset = self._apply_sorting(queryset, sort_by, order)
        
        # Get total count
        total_count = queryset.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        offers = queryset[offset:offset + page_size]
        
        # Serialize results
        results = [self._serialize_offer(offer) for offer in offers]
        
        return {
            'results': results,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size,
            'has_next': offset + page_size < total_count,
            'has_previous': page > 1,
        }
    
    def _apply_text_search(self, queryset, query: str):
        """Apply text search to queryset"""
        search_terms = query.strip().split()
        
        if not search_terms:
            return queryset
        
        q_objects = []
        
        for term in search_terms:
            q_objects.append(
                Q(title__icontains=term) |
                Q(description__icontains=term) |
                Q(category__name__icontains=term) |
                Q(tags__name__icontains=term)
            )
        
        # Combine with OR for any term match
        combined_q = q_objects[0]
        for q_obj in q_objects[1:]:
            combined_q |= q_obj
        
        return queryset.filter(combined_q).distinct()
    
    def _apply_filters(self, queryset, filters: Dict):
        """Apply filters to queryset"""
        # Category filter
        if 'category_id' in filters:
            queryset = queryset.filter(category_id=filters['category_id'])
        
        # Reward amount filter
        if 'min_reward' in filters:
            queryset = queryset.filter(reward_amount__gte=filters['min_reward'])
        if 'max_reward' in filters:
            queryset = queryset.filter(reward_amount__lte=filters['max_reward'])
        
        # Platform filter
        if 'platforms' in filters:
            platforms = filters['platforms']
            if isinstance(platforms, str):
                platforms = [platforms]
            queryset = queryset.filter(platforms__overlap=platforms)
        
        # Device type filter
        if 'device_type' in filters:
            queryset = queryset.filter(device_type=filters['device_type'])
        
        # Difficulty filter
        if 'difficulty' in filters:
            difficulty = filters['difficulty']
            if isinstance(difficulty, str):
                difficulty = [difficulty]
            queryset = queryset.filter(difficulty__in=difficulty)
        
        # Country filter
        if 'countries' in filters:
            countries = filters['countries']
            if isinstance(countries, str):
                countries = [countries]
            queryset = queryset.filter(countries__overlap=countries)
        
        # Tags filter
        if 'tags' in filters:
            tags = filters['tags']
            if isinstance(tags, str):
                tags = [tags]
            queryset = queryset.filter(tags__name__in=tags).distinct()
        
        # Featured filter
        if 'is_featured' in filters:
            queryset = queryset.filter(is_featured=filters['is_featured'])
        
        # Hot offers filter
        if 'is_hot' in filters:
            queryset = queryset.filter(is_hot=filters['is_hot'])
        
        # New offers filter
        if 'is_new' in filters:
            queryset = queryset.filter(is_new=filters['is_new'])
        
        # Time-based filters
        if 'created_after' in filters:
            queryset = queryset.filter(created_at__gte=filters['created_after'])
        if 'created_before' in filters:
            queryset = queryset.filter(created_at__lte=filters['created_before'])
        
        # Expiration filter
        if 'expires_after' in filters:
            queryset = queryset.filter(expires_at__gte=filters['expires_after'])
        if 'expires_before' in filters:
            queryset = queryset.filter(expires_at__lte=filters['expires_before'])
        
        return queryset
    
    def _apply_sorting(self, queryset, sort_by: str, order: str):
        """Apply sorting to queryset"""
        valid_sort_fields = {
            'created_at', 'updated_at', 'title', 'reward_amount',
            'total_conversions', 'conversion_rate', 'performance_score',
            'starts_at', 'expires_at', 'clicks_count'
        }
        
        if sort_by not in valid_sort_fields:
            sort_by = 'created_at'
        
        if order.lower() == 'desc':
            sort_field = f'-{sort_by}'
        else:
            sort_field = sort_by
        
        return queryset.order_by(sort_field)
    
    def _serialize_offer(self, offer) -> Dict[str, Any]:
        """Serialize offer for search results"""
        return {
            'id': offer.id,
            'title': offer.title,
            'description': offer.description[:200] + '...' if len(offer.description) > 200 else offer.description,
            'reward_amount': float(offer.reward_amount),
            'reward_currency': offer.reward_currency,
            'category': {
                'id': offer.category.id,
                'name': offer.category.name
            } if offer.category else None,
            'platforms': offer.platforms,
            'device_type': offer.device_type,
            'difficulty': offer.difficulty,
            'estimated_time': offer.estimated_time,
            'is_featured': offer.is_featured,
            'is_hot': offer.is_hot,
            'is_new': offer.is_new,
            'tags': [{'name': tag.name, 'color': tag.color} for tag in offer.tags.all()],
            'created_at': offer.created_at.isoformat(),
            'expires_at': offer.expires_at.isoformat() if offer.expires_at else None,
            'performance_score': offer.performance_score,
            'total_conversions': offer.total_conversions,
            'conversion_rate': offer.conversion_rate,
            'click_url': offer.click_url,
            'preview_url': offer.preview_url,
        }


class UserSearchEngine:
    """Search engine for user-related data"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
    
    def search_user_engagements(self, user_id: int, query: str = None, 
                               filters: Dict = None) -> List[Dict[str, Any]]:
        """Search user's offer engagements"""
        queryset = UserOfferEngagement.objects.filter(
            tenant_id=self.tenant_id,
            user_id=user_id
        )
        
        # Apply text search
        if query:
            queryset = queryset.filter(
                Q(offer__title__icontains=query) |
                Q(offer__description__icontains=query)
            )
        
        # Apply filters
        if filters:
            if 'status' in filters:
                queryset = queryset.filter(status=filters['status'])
            if 'start_date' in filters:
                queryset = queryset.filter(created_at__gte=filters['start_date'])
            if 'end_date' in filters:
                queryset = queryset.filter(created_at__lte=filters['end_date'])
        
        # Serialize results
        results = []
        for engagement in queryset.select_related('offer').order_by('-created_at'):
            results.append({
                'id': engagement.id,
                'offer': {
                    'id': engagement.offer.id,
                    'title': engagement.offer.title,
                    'reward_amount': float(engagement.offer.reward_amount),
                    'reward_currency': engagement.offer.reward_currency,
                },
                'status': engagement.status,
                'created_at': engagement.created_at.isoformat(),
                'started_at': engagement.started_at.isoformat() if engagement.started_at else None,
                'completed_at': engagement.completed_at.isoformat() if engagement.completed_at else None,
                'conversion': {
                    'id': engagement.conversion.id,
                    'status': engagement.conversion.status,
                    'payout': float(engagement.conversion.payout) if engagement.conversion else None,
                } if hasattr(engagement, 'conversion') and engagement.conversion else None,
            })
        
        return results
    
    def search_user_conversions(self, user_id: int, query: str = None, 
                              filters: Dict = None) -> List[Dict[str, Any]]:
        """Search user's conversions"""
        queryset = OfferConversion.objects.filter(
            tenant_id=self.tenant_id,
            engagement__user_id=user_id
        ).select_related('engagement__offer')
        
        # Apply text search
        if query:
            queryset = queryset.filter(
                Q(engagement__offer__title__icontains=query) |
                Q(engagement__offer__description__icontains=query)
            )
        
        # Apply filters
        if filters:
            if 'status' in filters:
                queryset = queryset.filter(status=filters['status'])
            if 'start_date' in filters:
                queryset = queryset.filter(created_at__gte=filters['start_date'])
            if 'end_date' in filters:
                queryset = queryset.filter(created_at__lte=filters['end_date'])
            if 'min_payout' in filters:
                queryset = queryset.filter(payout__gte=filters['min_payout'])
            if 'max_payout' in filters:
                queryset = queryset.filter(payout__lte=filters['max_payout'])
        
        # Serialize results
        results = []
        for conversion in queryset.order_by('-created_at'):
            results.append({
                'id': conversion.id,
                'offer': {
                    'id': conversion.engagement.offer.id,
                    'title': conversion.engagement.offer.title,
                },
                'status': conversion.status,
                'payout': float(conversion.payout),
                'currency': conversion.currency,
                'created_at': conversion.created_at.isoformat(),
                'approved_at': conversion.approved_at.isoformat() if conversion.approved_at else None,
                'fraud_score': conversion.fraud_score,
                'is_fraud': conversion.is_fraud,
            })
        
        return results
    
    def search_user_rewards(self, user_id: int, query: str = None, 
                           filters: Dict = None) -> List[Dict[str, Any]]:
        """Search user's rewards"""
        queryset = OfferReward.objects.filter(
            tenant_id=self.tenant_id,
            user_id=user_id
        ).select_related('offer')
        
        # Apply text search
        if query:
            queryset = queryset.filter(
                Q(offer__title__icontains=query) |
                Q(offer__description__icontains=query)
            )
        
        # Apply filters
        if filters:
            if 'status' in filters:
                queryset = queryset.filter(status=filters['status'])
            if 'start_date' in filters:
                queryset = queryset.filter(created_at__gte=filters['start_date'])
            if 'end_date' in filters:
                queryset = queryset.filter(created_at__lte=filters['end_date'])
            if 'min_amount' in filters:
                queryset = queryset.filter(amount__gte=filters['min_amount'])
            if 'max_amount' in filters:
                queryset = queryset.filter(amount__lte=filters['max_amount'])
        
        # Serialize results
        results = []
        for reward in queryset.order_by('-created_at'):
            results.append({
                'id': reward.id,
                'offer': {
                    'id': reward.offer.id,
                    'title': reward.offer.title,
                },
                'amount': float(reward.amount),
                'currency': reward.currency,
                'commission': float(reward.commission) if reward.commission else None,
                'status': reward.status,
                'created_at': reward.created_at.isoformat(),
                'approved_at': reward.approved_at.isoformat() if reward.approved_at else None,
                'paid_at': reward.paid_at.isoformat() if reward.paid_at else None,
                'payment_method': reward.payment_method,
                'payment_reference': reward.payment_reference,
            })
        
        return results


class AnalyticsSearchEngine:
    """Search engine for analytics data"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
    
    def search_performance_data(self, filters: Dict = None) -> Dict[str, Any]:
        """Search performance analytics data"""
        # Base date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        
        if filters:
            if 'start_date' in filters:
                start_date = filters['start_date']
            if 'end_date' in filters:
                end_date = filters['end_date']
        
        # Get offer performance data
        offers = Offer.objects.filter(
            tenant_id=self.tenant_id,
            created_at__range=[start_date, end_date]
        ).annotate(
            total_clicks=Count('userofferengagement'),
            total_conversions=Count('userofferengagement__offerconversion'),
            total_payout=Sum('userofferengagement__offerconversion__payout'),
            conversion_rate=ExpressionWrapper(
                Count('userofferengagement__offerconversion') * 100.0 / Count('userofferengagement'),
                output_field=FloatField()
            )
        ).order_by('-total_conversions')
        
        # Serialize results
        results = []
        for offer in offers:
            results.append({
                'id': offer.id,
                'title': offer.title,
                'total_clicks': offer.total_clicks,
                'total_conversions': offer.total_conversions,
                'total_payout': float(offer.total_payout) if offer.total_payout else 0,
                'conversion_rate': float(offer.conversion_rate) if offer.conversion_rate else 0,
                'performance_score': offer.performance_score,
            })
        
        return {
            'results': results,
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
            },
            'summary': {
                'total_offers': len(results),
                'total_clicks': sum(r['total_clicks'] for r in results),
                'total_conversions': sum(r['total_conversions'] for r in results),
                'total_payout': sum(r['total_payout'] for r in results),
                'avg_conversion_rate': calculate_percentage(
                    sum(r['total_conversions'] for r in results),
                    sum(r['total_clicks'] for r in results)
                ) if results else 0,
            }
        }
    
    def search_network_statistics(self, filters: Dict = None) -> List[Dict[str, Any]]:
        """Search network statistics"""
        queryset = AdNetwork.objects.filter(tenant_id=self.tenant_id)
        
        # Apply filters
        if filters:
            if 'category' in filters:
                queryset = queryset.filter(category=filters['category'])
            if 'status' in filters:
                queryset = queryset.filter(status=filters['status'])
            if 'is_active' in filters:
                queryset = queryset.filter(is_active=filters['is_active'])
        
        # Annotate with statistics
        queryset = queryset.annotate(
            total_offers=Count('offer'),
            active_offers=Count('offer', filter=Q(offer__status=OfferStatus.ACTIVE)),
            total_conversions=Count('offer__userofferengagement__offerconversion'),
            total_payout=Sum('offer__userofferengagement__offerconversion__payout')
        )
        
        # Serialize results
        results = []
        for network in queryset:
            results.append({
                'id': network.id,
                'name': network.name,
                'network_type': network.network_type,
                'category': network.category,
                'status': network.status,
                'is_active': network.is_active,
                'total_offers': network.total_offers,
                'active_offers': network.active_offers,
                'total_conversions': network.total_conversions,
                'total_payout': float(network.total_payout) if network.total_payout else 0,
                'success_rate': network.success_rate,
                'avg_payout': float(network.avg_payout) if network.avg_payout else 0,
                'last_sync': network.last_sync.isoformat() if network.last_sync else None,
            })
        
        return results


class GlobalSearchEngine:
    """Global search across all entities"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.offer_search = OfferSearchEngine(tenant_id)
        self.user_search = UserSearchEngine(tenant_id)
        self.analytics_search = AnalyticsSearchEngine(tenant_id)
    
    def search(self, query: str, entity_type: str = 'all', filters: Dict = None) -> Dict[str, Any]:
        """
        Global search across all entities
        """
        results = {
            'query': query,
            'entity_type': entity_type,
            'results': {}
        }
        
        if entity_type in ['all', 'offers']:
            results['results']['offers'] = self.offer_search.search_offers(
                query=query,
                filters=filters,
                page=1,
                page_size=10
            )
        
        if entity_type in ['all', 'engagements']:
            # This would require user_id, so we'll skip for global search
            pass
        
        if entity_type in ['all', 'analytics']:
            results['results']['analytics'] = self.analytics_search.search_performance_data(
                filters=filters
            )
        
        return results


# ==================== SEARCH INDEXING ====================

class SearchIndexManager:
    """Manage search indexing for offers"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
    
    def index_offer(self, offer_id: int) -> bool:
        """Index offer for search"""
        try:
            offer = Offer.objects.get(id=offer_id, tenant_id=self.tenant_id)
            
            # Create search document
            document = {
                'id': offer.id,
                'title': offer.title,
                'description': offer.description,
                'category': offer.category.name if offer.category else '',
                'tags': [tag.name for tag in offer.tags.all()],
                'platforms': offer.platforms,
                'device_type': offer.device_type,
                'difficulty': offer.difficulty,
                'reward_amount': float(offer.reward_amount),
                'created_at': offer.created_at.isoformat(),
                'updated_at': offer.updated_at.isoformat(),
            }
            
            # Store in cache (in production, use Elasticsearch or similar)
            cache_key = f"search_index_offer_{offer.id}"
            cache.set(cache_key, document, timeout=3600)
            
            return True
            
        except Exception as e:
            logger.error(f"Error indexing offer {offer_id}: {str(e)}")
            return False
    
    def remove_from_index(self, offer_id: int) -> bool:
        """Remove offer from search index"""
        try:
            cache_key = f"search_index_offer_{offer_id}"
            cache.delete(cache_key)
            return True
        except Exception as e:
            logger.error(f"Error removing offer {offer_id} from index: {str(e)}")
            return False
    
    def rebuild_index(self) -> int:
        """Rebuild entire search index"""
        indexed_count = 0
        
        try:
            offers = Offer.objects.filter(tenant_id=self.tenant_id)
            
            for offer in offers:
                if self.index_offer(offer.id):
                    indexed_count += 1
            
            logger.info(f"Rebuilt search index for {indexed_count} offers")
            
        except Exception as e:
            logger.error(f"Error rebuilding search index: {str(e)}")
        
        return indexed_count


# ==================== SEARCH SUGGESTIONS ====================

class SearchSuggestions:
    """Provide search suggestions"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.cache_timeout = CACHE_TIMEOUTS.get('search_suggestions', 1800)
    
    def get_offer_suggestions(self, query: str, limit: int = 10) -> List[str]:
        """Get offer title suggestions"""
        if len(query) < 2:
            return []
        
        cache_key = get_cache_key('offer_suggestions', query, limit)
        suggestions = cache.get(cache_key)
        
        if suggestions is None:
            # Get matching offers
            offers = Offer.objects.filter(
                tenant_id=self.tenant_id,
                title__icontains=query,
                status=OfferStatus.ACTIVE
            ).values_list('title', flat=True)[:limit]
            
            suggestions = list(offers)
            cache.set(cache_key, suggestions, self.cache_timeout)
        
        return suggestions
    
    def get_tag_suggestions(self, query: str, limit: int = 10) -> List[str]:
        """Get tag suggestions"""
        if len(query) < 2:
            return []
        
        cache_key = get_cache_key('tag_suggestions', query, limit)
        suggestions = cache.get(cache_key)
        
        if suggestions is None:
            # Get matching tags
            tags = OfferTag.objects.filter(
                tenant_id=self.tenant_id,
                name__icontains=query,
                is_active=True
            ).values_list('name', flat=True)[:limit]
            
            suggestions = list(tags)
            cache.set(cache_key, suggestions, self.cache_timeout)
        
        return suggestions
    
    def get_category_suggestions(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get category suggestions"""
        if len(query) < 2:
            return []
        
        cache_key = get_cache_key('category_suggestions', query, limit)
        suggestions = cache.get(cache_key)
        
        if suggestions is None:
            # Get matching categories
            categories = OfferCategory.objects.filter(
                name__icontains=query
            ).annotate(
                offer_count=Count('offer')
            ).filter(offer_count__gt=0)[:limit]
            
            suggestions = [
                {
                    'id': cat.id,
                    'name': cat.name,
                    'offer_count': cat.offer_count
                }
                for cat in categories
            ]
            cache.set(cache_key, suggestions, self.cache_timeout)
        
        return suggestions


# ==================== SEARCH ANALYTICS ====================

class SearchAnalytics:
    """Track search analytics"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
    
    def log_search(self, user_id: int, query: str, entity_type: str, 
                   results_count: int, filters: Dict = None) -> bool:
        """Log search query for analytics"""
        try:
            # In production, store in analytics database
            log_data = {
                'tenant_id': self.tenant_id,
                'user_id': user_id,
                'query': query,
                'entity_type': entity_type,
                'results_count': results_count,
                'filters': filters or {},
                'timestamp': timezone.now().isoformat(),
            }
            
            logger.info(f"Search logged: {log_data}")
            return True
            
        except Exception as e:
            logger.error(f"Error logging search: {str(e)}")
            return False
    
    def get_popular_searches(self, days: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
        """Get popular search queries"""
        # This would typically query a search analytics table
        # For now, return empty list
        return []
    
    def get_search_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get search statistics"""
        # This would typically query a search analytics table
        # For now, return empty stats
        return {
            'total_searches': 0,
            'unique_users': 0,
            'avg_results_per_search': 0,
            'top_queries': [],
        }


# ==================== EXPORTS ====================

__all__ = [
    'OfferSearchEngine',
    'UserSearchEngine',
    'AnalyticsSearchEngine',
    'GlobalSearchEngine',
    'SearchIndexManager',
    'SearchSuggestions',
    'SearchAnalytics',
]
