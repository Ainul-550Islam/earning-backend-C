# engagement/search.py
"""
Search functionality for engagement system.
Provides search capabilities across models and content.
"""
from django.db.models import Q, Count, Sum, Avg
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.utils import timezone
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from .models.checkin import DailyCheckIn
from .models.spinwheel import SpinWheel
from .models.quest import UserQuest, Quest
from .models.achievement import UserAchievement, Achievement
from .models.shop import ShopItem, ShopPurchase
from .models.leaderboard import Leaderboard
from .models.social import FeedItem
from .models.notification import Notification
from .models.referral import Referral


class EngagementSearchEngine:
    """Main search engine for engagement system."""
    
    def __init__(self):
        self.search_fields = {
            'checkins': ['user__username', 'note'],
            'spins': ['user__username'],
            'quests': ['user__username', 'quest__name', 'quest__description'],
            'achievements': ['user__username', 'achievement__name', 'achievement__description'],
            'shop_items': ['name', 'description'],
            'shop_purchases': ['user__username', 'item__name'],
            'leaderboard': ['user__username'],
            'feed_items': ['user__username', 'title', 'body'],
            'notifications': ['title', 'body'],
            'referrals': ['referrer__username', 'referred__username', 'referral_code'],
        }
    
    def search(self, query: str, models: List[str] = None, user=None, tenant=None, limit=50):
        """
        Perform search across specified models.
        
        Args:
            query: Search query string
            models: List of model names to search
            user: Filter by user
            tenant: Filter by tenant
            limit: Results limit per model
            
        Returns:
            Dictionary with search results
        """
        if not query or len(query.strip()) < 2:
            return {'error': 'Query too short', 'results': {}}
        
        if models is None:
            models = list(self.search_fields.keys())
        
        results = {}
        
        for model_name in models:
            if model_name in self.search_fields:
                model_results = self._search_model(model_name, query, user, tenant, limit)
                if model_results:
                    results[model_name] = model_results
        
        return {'results': results, 'query': query}
    
    def _search_model(self, model_name: str, query: str, user=None, tenant=None, limit=50):
        """Search specific model."""
        try:
            model_class = self._get_model_class(model_name)
            if not model_class:
                return []
            
            # Build search query
            search_fields = self.search_fields[model_name]
            q_objects = []
            
            for field in search_fields:
                q_objects.append(Q(**{f"{field}__icontains": query}))
            
            combined_q = Q()
            for q_obj in q_objects:
                combined_q |= q_obj
            
            # Apply filters
            queryset = model_class.objects.filter(combined_q)
            
            if user:
                queryset = queryset.filter(user=user)
            
            if tenant:
                queryset = queryset.filter(tenant=tenant)
            
            # Limit results
            results = list(queryset[:limit])
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append(self._format_search_result(result, model_name))
            
            return formatted_results
            
        except Exception as exc:
            return []
    
    def _get_model_class(self, model_name: str):
        """Get model class by name."""
        model_map = {
            'checkins': DailyCheckIn,
            'spins': SpinWheel,
            'quests': UserQuest,
            'achievements': UserAchievement,
            'shop_items': ShopItem,
            'shop_purchases': ShopPurchase,
            'leaderboard': Leaderboard,
            'feed_items': FeedItem,
            'notifications': Notification,
            'referrals': Referral,
        }
        return model_map.get(model_name)
    
    def _format_search_result(self, result, model_name: str):
        """Format search result."""
        base_result = {
            'id': result.id,
            'model': model_name,
            'created_at': result.created_at.isoformat() if hasattr(result, 'created_at') else None,
        }
        
        # Add model-specific fields
        if model_name == 'checkins':
            base_result.update({
                'user': result.user.username if result.user else None,
                'date': result.date.isoformat() if result.date else None,
                'coins_earned': float(result.coins_earned) if result.coins_earned else 0,
                'xp_earned': result.xp_earned or 0,
                'streak': result.consecutive_days or 0,
                'note': result.note or '',
            })
        elif model_name == 'spins':
            base_result.update({
                'user': result.user.username if result.user else None,
                'spun_at': result.spun_at.isoformat() if result.spun_at else None,
                'coins_won': float(result.coins_won) if result.coins_won else 0,
                'xp_earned': result.xp_earned or 0,
                'is_boosted': result.is_boosted or False,
            })
        elif model_name == 'quests':
            base_result.update({
                'user': result.user.username if result.user else None,
                'quest_name': result.quest.name if result.quest else None,
                'quest_description': result.quest.description if result.quest else None,
                'status': result.status,
                'progress': result.progress or 0,
            })
        elif model_name == 'achievements':
            base_result.update({
                'user': result.user.username if result.user else None,
                'achievement_name': result.achievement.name if result.achievement else None,
                'achievement_description': result.achievement.description if result.achievement else None,
                'progress': result.progress or 0,
                'unlocked_at': result.unlocked_at.isoformat() if result.unlocked_at else None,
            })
        elif model_name == 'shop_items':
            base_result.update({
                'name': result.name,
                'description': result.description,
                'price': float(result.price) if result.price else 0,
                'type': result.type,
                'rarity': result.rarity,
            })
        elif model_name == 'shop_purchases':
            base_result.update({
                'user': result.user.username if result.user else None,
                'item_name': result.item.name if result.item else None,
                'quantity': result.quantity,
                'coins_spent': float(result.coins_spent) if result.coins_spent else 0,
                'status': result.status,
                'purchased_at': result.purchased_at.isoformat() if result.purchased_at else None,
            })
        elif model_name == 'leaderboard':
            base_result.update({
                'user': result.user.username if result.user else None,
                'date': result.date.isoformat() if result.date else None,
                'rank': result.rank,
                'total_coins_earned': float(result.total_coins_earned) if result.total_coins_earned else 0,
                'total_xp_earned': result.total_xp_earned or 0,
            })
        elif model_name == 'feed_items':
            base_result.update({
                'user': result.user.username if result.user else None,
                'feed_type': result.feed_type,
                'title': result.title,
                'body': result.body,
                'likes_count': result.likes_count or 0,
                'comments_count': result.comments_count or 0,
            })
        elif model_name == 'notifications':
            base_result.update({
                'user': result.user.username if result.user else None,
                'type': result.type,
                'title': result.title,
                'body': result.body,
                'is_read': result.is_read,
                'created_at': result.created_at.isoformat() if result.created_at else None,
            })
        elif model_name == 'referrals':
            base_result.update({
                'referrer': result.referrer.username if result.referrer else None,
                'referred': result.referred.username if result.referred else None,
                'referral_code': result.referral_code,
                'status': result.status,
                'created_at': result.created_at.isoformat() if result.created_at else None,
            })
        
        return base_result


class AdvancedSearchEngine(EngagementSearchEngine):
    """Advanced search engine with full-text search and analytics."""
    
    def __init__(self):
        super().__init__()
        self.analytics_fields = {
            'user_activity': ['user__username', 'action_type'],
            'quest_completion': ['quest__name', 'quest__description'],
            'achievement_unlock': ['achievement__name', 'achievement__description'],
            'shop_activity': ['item__name', 'item__description'],
            'social_activity': ['title', 'body'],
        }
    
    def full_text_search(self, query: str, models: List[str] = None, user=None, tenant=None, limit=50):
        """
        Perform full-text search using PostgreSQL search.
        """
        if not query or len(query.strip()) < 2:
            return {'error': 'Query too short', 'results': {}}
        
        if models is None:
            models = ['quests', 'achievements', 'shop_items', 'feed_items']
        
        results = {}
        
        for model_name in models:
            if model_name in self.analytics_fields:
                model_results = self._full_text_search_model(model_name, query, user, tenant, limit)
                if model_results:
                    results[model_name] = model_results
        
        return {'results': results, 'query': query}
    
    def _full_text_search_model(self, model_name: str, query: str, user=None, tenant=None, limit=50):
        """Perform full-text search on specific model."""
        try:
            model_class = self._get_model_class(model_name)
            if not model_class:
                return []
            
            # Build search vector and query
            search_fields = self.analytics_fields[model_name]
            search_vector = SearchVector(*search_fields)
            search_query = SearchQuery(query)
            
            # Apply search
            queryset = model_class.objects.annotate(
                rank=SearchRank(search_vector, search_query)
            ).filter(search_vector=search_query)
            
            if user:
                queryset = queryset.filter(user=user)
            
            if tenant:
                queryset = queryset.filter(tenant=tenant)
            
            # Order by rank and limit
            results = list(queryset.order_by('-rank')[:limit])
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_result = self._format_search_result(result, model_name)
                formatted_result['search_rank'] = result.rank
                formatted_results.append(formatted_result)
            
            return formatted_results
            
        except Exception as exc:
            return []
    
    def search_analytics(self, query: str, date_from=None, date_to=None, user=None, tenant=None):
        """
        Search analytics data with time range filtering.
        """
        try:
            # Get engagement events
            from .models.analytics import EngagementEvent
            
            queryset = EngagementEvent.objects.filter(
                properties__icontains=query
            )
            
            if user:
                queryset = queryset.filter(user=user)
            
            if tenant:
                queryset = queryset.filter(tenant=tenant)
            
            if date_from:
                queryset = queryset.filter(created_at__date__gte=date_from)
            
            if date_to:
                queryset = queryset.filter(created_at__date__lte=date_to)
            
            # Group by event type
            results = queryset.values('event_type').annotate(
                count=Count('id'),
                avg_value=Avg('value'),
                total_value=Sum('value')
            ).order_by('-count')
            
            return {
                'results': list(results),
                'query': query,
                'date_range': {
                    'from': date_from.isoformat() if date_from else None,
                    'to': date_to.isoformat() if date_to else None,
                }
            }
            
        except Exception as exc:
            return {'error': str(exc), 'results': []}
    
    def search_suggestions(self, query: str, limit=10):
        """
        Get search suggestions based on partial query.
        """
        if not query or len(query) < 2:
            return []
        
        suggestions = []
        
        # Get quest name suggestions
        quest_names = Quest.objects.filter(
            name__icontains=query
        ).values_list('name', flat=True)[:limit//2]
        
        for name in quest_names:
            suggestions.append({
                'type': 'quest',
                'text': name,
                'highlight': self._highlight_text(name, query)
            })
        
        # Get achievement name suggestions
        achievement_names = Achievement.objects.filter(
            name__icontains=query
        ).values_list('name', flat=True)[:limit//2]
        
        for name in achievement_names:
            suggestions.append({
                'type': 'achievement',
                'text': name,
                'highlight': self._highlight_text(name, query)
            })
        
        return suggestions[:limit]
    
    def _highlight_text(self, text: str, query: str):
        """Highlight matching text."""
        query_lower = query.lower()
        text_lower = text.lower()
        
        start_index = text_lower.find(query_lower)
        if start_index == -1:
            return text
        
        end_index = start_index + len(query)
        
        # Extract context around match
        context_start = max(0, start_index - 20)
        context_end = min(len(text), end_index + 20)
        
        highlighted = text[context_start:context_end]
        
        # Add ellipsis if truncated
        if context_start > 0:
            highlighted = '...' + highlighted
        if context_end < len(text):
            highlighted = highlighted + '...'
        
        return highlighted


class UserSearchEngine:
    """Search engine for user-specific content."""
    
    def __init__(self, user):
        self.user = user
        self.base_engine = EngagementSearchEngine()
    
    def search_my_content(self, query: str, models: List[str] = None, limit=50):
        """Search user's own content."""
        return self.base_engine.search(
            query=query,
            models=models,
            user=self.user,
            limit=limit
        )
    
    def search_my_activity(self, query: str, date_from=None, date_to=None, limit=50):
        """Search user's activity history."""
        try:
            # Get user's activity events
            from .models.analytics import EngagementEvent
            
            queryset = EngagementEvent.objects.filter(
                user=self.user,
                properties__icontains=query
            )
            
            if date_from:
                queryset = queryset.filter(created_at__date__gte=date_from)
            
            if date_to:
                queryset = queryset.filter(created_at__date__lte=date_to)
            
            results = list(queryset.order_by('-created_at')[:limit])
            
            formatted_results = []
            for result in results:
                formatted_results.append({
                    'id': result.id,
                    'event_type': result.event_type,
                    'properties': result.properties,
                    'created_at': result.created_at.isoformat(),
                    'value': result.value,
                })
            
            return {
                'results': formatted_results,
                'query': query,
                'date_range': {
                    'from': date_from.isoformat() if date_from else None,
                    'to': date_to.isoformat() if date_to else None,
                }
            }
            
        except Exception as exc:
            return {'error': str(exc), 'results': []}
    
    def search_my_achievements(self, query: str, unlocked_only=False, limit=50):
        """Search user's achievements."""
        try:
            queryset = UserAchievement.objects.filter(
                user=self.user,
                achievement__name__icontains=query
            )
            
            if unlocked_only:
                queryset = queryset.filter(unlocked_at__isnull=False)
            
            results = list(queryset[:limit])
            
            formatted_results = []
            for result in results:
                formatted_results.append({
                    'id': result.id,
                    'achievement_name': result.achievement.name,
                    'achievement_description': result.achievement.description,
                    'progress': result.progress,
                    'unlocked_at': result.unlocked_at.isoformat() if result.unlocked_at else None,
                })
            
            return {
                'results': formatted_results,
                'query': query,
                'unlocked_only': unlocked_only
            }
            
        except Exception as exc:
            return {'error': str(exc), 'results': []}
    
    def search_my_purchases(self, query: str, limit=50):
        """Search user's shop purchases."""
        try:
            queryset = ShopPurchase.objects.filter(
                user=self.user,
                item__name__icontains=query
            )
            
            results = list(queryset[:limit])
            
            formatted_results = []
            for result in results:
                formatted_results.append({
                    'id': result.id,
                    'item_name': result.item.name,
                    'quantity': result.quantity,
                    'coins_spent': float(result.coins_spent),
                    'status': result.status,
                    'purchased_at': result.purchased_at.isoformat() if result.purchased_at else None,
                })
            
            return {
                'results': formatted_results,
                'query': query
            }
            
        except Exception as exc:
            return {'error': str(exc), 'results': []}


class AdminSearchEngine(EngagementSearchEngine):
    """Search engine for admin users with extended capabilities."""
    
    def search_users(self, query: str, limit=50):
        """Search users by username, email, etc."""
        try:
            from django.contrib.auth import get_user_model
            
            User = get_user_model()
            
            queryset = User.objects.filter(
                Q(username__icontains=query) |
                Q(email__icontains=query) |
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query)
            )
            
            results = list(queryset[:limit])
            
            formatted_results = []
            for result in results:
                formatted_results.append({
                    'id': result.id,
                    'username': result.username,
                    'email': result.email,
                    'first_name': result.first_name,
                    'last_name': result.last_name,
                    'is_active': result.is_active,
                    'date_joined': result.date_joined.isoformat() if result.date_joined else None,
                    'last_login': result.last_login.isoformat() if result.last_login else None,
                })
            
            return {
                'results': formatted_results,
                'query': query
            }
            
        except Exception as exc:
            return {'error': str(exc), 'results': []}
    
    def search_analytics(self, query: str, event_type=None, date_from=None, date_to=None, limit=100):
        """Search analytics data with advanced filtering."""
        try:
            from .models.analytics import EngagementEvent
            
            queryset = EngagementEvent.objects.filter(
                Q(event_type__icontains=query) |
                Q(properties__icontains=query)
            )
            
            if event_type:
                queryset = queryset.filter(event_type=event_type)
            
            if date_from:
                queryset = queryset.filter(created_at__date__gte=date_from)
            
            if date_to:
                queryset = queryset.filter(created_at__date__lte=date_to)
            
            results = list(queryset.order_by('-created_at')[:limit])
            
            formatted_results = []
            for result in results:
                formatted_results.append({
                    'id': result.id,
                    'user_id': result.user.id if result.user else None,
                    'username': result.user.username if result.user else None,
                    'event_type': result.event_type,
                    'properties': result.properties,
                    'created_at': result.created_at.isoformat(),
                    'value': result.value,
                })
            
            return {
                'results': formatted_results,
                'query': query,
                'filters': {
                    'event_type': event_type,
                    'date_from': date_from.isoformat() if date_from else None,
                    'date_to': date_to.isoformat() if date_to else None,
                }
            }
            
        except Exception as exc:
            return {'error': str(exc), 'results': []}
    
    def search_logs(self, query: str, level=None, date_from=None, date_to=None, limit=100):
        """Search system logs."""
        try:
            # This would integrate with your logging system
            # For now, return a placeholder
            return {
                'results': [],
                'query': query,
                'message': 'Log search not implemented'
            }
            
        except Exception as exc:
            return {'error': str(exc), 'results': []}


# ── Search Utilities ─────────────────────────────────────────────────────

def get_search_engine(user=None, engine_type='basic'):
    """Get appropriate search engine based on user and type."""
    if user and user.is_staff:
        if engine_type == 'advanced':
            return AdvancedSearchEngine()
        else:
            return AdminSearchEngine()
    elif user:
        if engine_type == 'advanced':
            return AdvancedSearchEngine()
        else:
            return UserSearchEngine(user)
    else:
        if engine_type == 'advanced':
            return AdvancedSearchEngine()
        else:
            return EngagementSearchEngine()


def format_search_response(results, query, pagination=None):
    """Format search response for API."""
    response = {
        'success': True,
        'query': query,
        'results': results,
        'total_count': sum(len(model_results) for model_results in results.values()),
    }
    
    if pagination:
        response['pagination'] = pagination
    
    return response


def build_search_query(query: str, exact_match=False, fuzzy_match=False):
    """Build search query with different matching options."""
    if not query:
        return Q()
    
    if exact_match:
        return Q(**{'name__iexact': query})
    elif fuzzy_match:
        # Implement fuzzy matching logic
        return Q(**{'name__icontains': query})
    else:
        return Q(**{'name__icontains': query})


def extract_search_terms(query: str):
    """Extract individual search terms from query."""
    import re
    
    # Split on spaces and quotes
    terms = re.findall(r'"[^"]*"|\S+', query)
    
    # Remove quotes from quoted terms
    cleaned_terms = []
    for term in terms:
        if term.startswith('"') and term.endswith('"'):
            cleaned_terms.append(term[1:-1])
        else:
            cleaned_terms.append(term)
    
    return cleaned_terms


def calculate_search_relevance(result, query_terms):
    """Calculate relevance score for search result."""
    score = 0
    
    for term in query_terms:
        # Check if term appears in different fields
        if hasattr(result, 'name') and term.lower() in result.name.lower():
            score += 10
        if hasattr(result, 'description') and term.lower() in result.description.lower():
            score += 5
        if hasattr(result, 'title') and term.lower() in result.title.lower():
            score += 8
        if hasattr(result, 'body') and term.lower() in result.body.lower():
            score += 3
    
    return score


def sort_results_by_relevance(results, query_terms):
    """Sort search results by relevance."""
    scored_results = []
    
    for result in results:
        relevance = calculate_search_relevance(result, query_terms)
        scored_results.append((result, relevance))
    
    # Sort by relevance (descending)
    scored_results.sort(key=lambda x: x[1], reverse=True)
    
    return [result for result, score in scored_results]


# ── Search Index Management ─────────────────────────────────────────────────

class SearchIndexManager:
    """Manager for search indices and indexing operations."""
    
    def __init__(self):
        self.indices = {}
    
    def create_index(self, index_name: str, model_class, fields: List[str]):
        """Create search index for model."""
        self.indices[index_name] = {
            'model': model_class,
            'fields': fields,
            'last_updated': None,
        }
    
    def update_index(self, index_name: str):
        """Update search index."""
        if index_name not in self.indices:
            return False
        
        index_info = self.indices[index_name]
        model_class = index_info['model']
        fields = index_info['fields']
        
        # Get all objects and index them
        objects = model_class.objects.all()
        
        for obj in objects:
            self._index_object(obj, fields)
        
        index_info['last_updated'] = timezone.now()
        return True
    
    def _index_object(self, obj, fields: List[str]):
        """Index individual object."""
        # This would integrate with your search backend
        # For now, it's a placeholder
        pass
    
    def search_index(self, index_name: str, query: str, limit=50):
        """Search specific index."""
        if index_name not in self.indices:
            return []
        
        index_info = self.indices[index_name]
        model_class = index_info['model']
        fields = index_info['fields']
        
        # Build search query
        q_objects = []
        for field in fields:
            q_objects.append(Q(**{f"{field}__icontains": query}))
        
        combined_q = Q()
        for q_obj in q_objects:
            combined_q |= q_obj
        
        results = model_class.objects.filter(combined_q)[:limit]
        return list(results)
    
    def get_index_stats(self, index_name: str):
        """Get statistics for search index."""
        if index_name not in self.indices:
            return None
        
        index_info = self.indices[index_name]
        model_class = index_info['model']
        
        return {
            'model': model_class.__name__,
            'fields': index_info['fields'],
            'total_objects': model_class.objects.count(),
            'last_updated': index_info['last_updated'],
        }


# Global search index manager
search_index_manager = SearchIndexManager()
