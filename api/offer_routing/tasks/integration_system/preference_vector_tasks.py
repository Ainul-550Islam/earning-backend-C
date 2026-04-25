"""
Preference Vector Tasks

Periodic tasks for rebuilding user preference vectors
in the offer routing system.
"""

import logging
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.contrib.auth import get_user_model
from ..services.personalization import ContextSignalService
from ..services.analytics import analytics_service
from ..services.cache import cache_service
from ..models import UserPreferenceVector, UserOfferHistory
from ..constants import PREFERENCE_VECTOR_REBUILD_INTERVAL, PREFERENCE_VECTOR_CACHE_TIMEOUT
from ..exceptions import PersonalizationError

logger = logging.getLogger(__name__)

User = get_user_model()


class PreferenceVectorTask:
    """
    Task for rebuilding user preference vectors.
    
    Runs weekly to rebuild:
    - User preference vectors
    - Interest profiles
    - Behavioral patterns
    - Category preferences
    - Demographic preferences
    """
    
    def __init__(self):
        self.context_service = ContextSignalService()
        self.analytics_service = analytics_service
        self.cache_service = cache_service
        self.task_stats = {
            'total_rebuilds': 0,
            'successful_rebuilds': 0,
            'failed_rebuilds': 0,
            'avg_rebuild_time_ms': 0.0
        }
    
    def run_preference_vector_rebuild(self) -> Dict[str, Any]:
        """
        Run the preference vector rebuild task.
        
        Returns:
            Task execution results
        """
        try:
            start_time = timezone.now()
            
            # Get users that need preference vector rebuilds
            users_to_rebuild = self._get_users_needing_rebuild()
            
            if not users_to_rebuild:
                logger.info("No users need preference vector rebuilds")
                return {
                    'success': True,
                    'message': 'No users need preference vector rebuilds',
                    'users_rebuilt': 0,
                    'execution_time_ms': 0,
                    'timestamp': timezone.now().isoformat()
                }
            
            # Rebuild preference vectors for each user
            rebuilt_users = 0
            failed_users = 0
            
            for user in users_to_rebuild:
                try:
                    # Rebuild user's preference vector
                    result = self._rebuild_user_preference_vector(user)
                    
                    if result['success']:
                        rebuilt_users += 1
                        logger.info(f"Rebuilt preference vector for user {user.id}")
                    else:
                        failed_users += 1
                        logger.error(f"Failed to rebuild preference vector for user {user.id}: {result['error']}")
                        
                except Exception as e:
                    failed_users += 1
                    logger.error(f"Error rebuilding preference vector for user {user.id}: {e}")
            
            # Update task statistics
            self._update_task_stats(start_time)
            
            # Clear relevant cache
            self._clear_preference_cache(users_to_rebuild)
            
            return {
                'success': True,
                'message': 'Preference vector rebuild task completed',
                'users_rebuilt': rebuilt_users,
                'users_failed': failed_users,
                'total_users': len(users_to_rebuild),
                'execution_time_ms': (timezone.now() - start_time).total_seconds() * 1000,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in preference vector rebuild task: {e}")
            return {
                'success': False,
                'error': str(e),
                'execution_time_ms': 0,
                'timestamp': timezone.now().isoformat()
            }
    
    def _get_users_needing_rebuild(self) -> List[User]:
        """Get users that need preference vector rebuilds."""
        try:
            # Get users that haven't had preference vectors rebuilt recently
            cutoff_time = timezone.now() - timezone.timedelta(days=PREFERENCE_VECTOR_REBUILD_INTERVAL)
            
            users = User.objects.filter(
                is_active=True,
                Q(userpreferencevector__rebuilt_at__lt=cutoff_time) | Q(userpreferencevector__isnull=True)
            ).order_by('-last_login')[:100]  # Limit to 100 users per batch
            
            # Prioritize users with recent activity
            recent_activity_cutoff = timezone.now() - timezone.timedelta(hours=6)
            active_users = UserOfferHistory.objects.filter(
                user__in=[user.id for user in users],
                created_at__gte=recent_activity_cutoff
            ).values_list('user_id').distinct()
            
            # Prioritize active users
            prioritized_users = []
            for user in users:
                if user.id in [active_user['user_id'] for active_user in active_users]:
                    prioritized_users.insert(0, user)
                else:
                    prioritized_users.append(user)
            
            return prioritized_users[:50]  # Limit to 50 total users
            
        except Exception as e:
            logger.error(f"Error getting users needing preference vector rebuild: {e}")
            return []
    
    def _rebuild_user_preference_vector(self, user: User) -> Dict[str, Any]:
        """Rebuild preference vector for a specific user."""
        try:
            # Get user's offer history
            offer_history = UserOfferHistory.objects.filter(
                user=user,
                created_at__gte=timezone.now() - timezone.timedelta(days=90)
            ).order_by('-created_at')
            
            # Extract preference data
            preference_data = self._extract_preference_data(user, offer_history)
            
            # Generate preference vector
            preference_vector = self._generate_preference_vector(preference_data)
            
            # Save preference vector
            with transaction.atomic():
                # Update existing or create new preference vector
                preference_vector_record, created = UserPreferenceVector.objects.update_or_create(
                    user=user,
                    defaults={
                        'preference_vector': preference_vector,
                        'rebuilt_at': timezone.now(),
                        'version': self._get_vector_version(),
                        'data_points_count': len(offer_history),
                        'categories_count': len(preference_data.get('categories', [])),
                        'interests_count': len(preference_data.get('interests', []))
                    }
                )
                
                if not created:
                    preference_vector_record.preference_vector = preference_vector
                    preference_vector_record.rebuilt_at = timezone.now()
                    preference_vector_record.version = self._get_vector_version()
                    preference_vector_record.data_points_count = len(offer_history)
                    preference_vector_record.categories_count = len(preference_data.get('categories', []))
                    preference_vector_record.interests_count = len(preference_data.get('interests', []))
                    preference_vector_record.save()
            
            # Update analytics
            self._update_preference_analytics(user, preference_vector, preference_data)
            
            # Update cache
            self._update_preference_cache(user, preference_vector)
            
            return {
                'success': True,
                'user_id': user.id,
                'previous_vector': preference_vector_record.preference_vector if not created else None,
                'new_vector': preference_vector,
                'data_points_used': len(offer_history),
                'categories_identified': len(preference_data.get('categories', [])),
                'interests_identified': len(preference_data.get('interests', [])),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error rebuilding preference vector for user {user.id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'user_id': user.id,
                'timestamp': timezone.now().isoformat()
            }
    
    def _extract_preference_data(self, user: User, offer_history) -> Dict[str, Any]:
        """Extract preference data from offer history."""
        try:
            # Analyze offer history for preferences
            categories = {}
            interests = {}
            behaviors = {}
            
            for history_item in offer_history:
                # Category preferences
                category = history_item.offer.category or 'general'
                if category not in categories:
                    categories[category] = {
                        'view_count': 0,
                        'click_count': 0,
                        'conversion_count': 0,
                        'total_value': 0.0,
                        'avg_score': 0.0
                    }
                
                category_data = categories[category]
                category_data['view_count'] += 1
                category_data['total_value'] += history_item.offer.price or 0.0
                category_data['avg_score'] = (category_data['avg_score'] * (category_data['view_count'] - 1) + (history_item.score_at_time or 0.0)) / category_data['view_count']
                
                if history_item.clicked_at:
                    category_data['click_count'] += 1
                
                if history_item.completed_at:
                    category_data['conversion_count'] += 1
            
            # Interest preferences (from offer names and descriptions)
            for history_item in offer_history:
                if history_item.clicked_at:
                    # Extract keywords from offer name
                    keywords = self._extract_keywords(history_item.offer.name)
                    for keyword in keywords:
                        interests[keyword] = interests.get(keyword, 0) + 1
            
            # Behavioral patterns
            behaviors = {
                'peak_activity_hours': self._analyze_activity_hours(offer_history),
                'preferred_price_range': self._analyze_price_preferences(offer_history),
                'offer_type_preferences': self._analyze_offer_type_preferences(offer_history),
                'response_time_preferences': self._analyze_response_time_patterns(offer_history)
            }
            
            return {
                'categories': categories,
                'interests': interests,
                'behaviors': behaviors,
                'data_points_count': len(offer_history),
                'time_span_days': (timezone.now() - (offer_history[0].created_at if offer_history else timezone.now())).days
            }
            
        except Exception as e:
            logger.error(f"Error extracting preference data for user {user.id}: {e}")
            return {}
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        try:
            # Simple keyword extraction
            import re
            
            # Common offer-related keywords
            keywords = [
                'discount', 'sale', 'offer', 'deal', 'promo', 'coupon',
                'free', 'bonus', 'reward', 'cashback', 'savings',
                'electronics', 'fashion', 'home', 'travel', 'food',
                'entertainment', 'gaming', 'shopping', 'online', 'mobile'
            ]
            
            # Extract keywords from text
            text_lower = text.lower()
            found_keywords = []
            
            for keyword in keywords:
                if keyword in text_lower:
                    found_keywords.append(keyword)
            
            return found_keywords
            
        except Exception as e:
            logger.error(f"Error extracting keywords: {e}")
            return []
    
    def _analyze_activity_hours(self, offer_history) -> List[int]:
        """Analyze user's peak activity hours."""
        try:
            hour_counts = [0] * 24  # 24 hours in a day
            
            for history_item in offer_history:
                if history_item.created_at:
                    hour = history_item.created_at.hour
                    hour_counts[hour] += 1
            
            # Find peak hours (top 25% of activity)
            total_activities = sum(hour_counts)
            threshold = total_activities * 0.25
            
            peak_hours = []
            for hour, count in enumerate(hour_counts):
                if count >= threshold:
                    peak_hours.append(hour)
            
            return peak_hours
            
        except Exception as e:
            logger.error(f"Error analyzing activity hours: {e}")
            return []
    
    def _analyze_price_preferences(self, offer_history) -> Dict[str, Any]:
        """Analyze user's price preferences."""
        try:
            prices = [item.offer.price for item in offer_history if item.offer.price and item.offer.price > 0]
            
            if not prices:
                return {
                    'min_price': 0.0,
                    'max_price': 0.0,
                    'avg_price': 0.0,
                    'preferred_range': '0-50'
                }
            
            min_price = min(prices)
            max_price = max(prices)
            avg_price = sum(prices) / len(prices)
            
            # Determine preferred price range
            if avg_price < 25:
                preferred_range = '0-25'
            elif avg_price < 50:
                preferred_range = '25-50'
            elif avg_price < 75:
                preferred_range = '50-75'
            elif avg_price < 100:
                preferred_range = '75-100'
            else:
                preferred_range = '100+'
            
            return {
                'min_price': min_price,
                'max_price': max_price,
                'avg_price': avg_price,
                'preferred_range': preferred_range
            }
            
        except Exception as e:
            logger.error(f"Error analyzing price preferences: {e}")
            return {}
    
    def _analyze_offer_type_preferences(self, offer_history) -> Dict[str, Any]:
        """Analyze user's offer type preferences."""
        try:
            offer_types = {}
            
            for history_item in offer_history:
                offer_type = history_item.offer.offer_type or 'standard'
                
                if offer_type not in offer_types:
                    offer_types[offer_type] = {
                        'count': 0,
                        'clicks': 0,
                        'conversions': 0
                    }
                
                offer_types[offer_type]['count'] += 1
                
                if history_item.clicked_at:
                    offer_types[offer_type]['clicks'] += 1
                
                if history_item.completed_at:
                    offer_types[offer_type]['conversions'] += 1
            
            # Find most preferred offer type
            most_preferred = None
            max_conversions = 0
            
            for offer_type, data in offer_types.items():
                if data['conversions'] > max_conversions:
                    max_conversions = data['conversions']
                    most_preferred = offer_type
            
            return {
                'offer_types': offer_types,
                'most_preferred': most_preferred,
                'max_conversions': max_conversions
            }
            
        except Exception as e:
            logger.error(f"Error analyzing offer type preferences: {e}")
            return {}
    
    def _analyze_response_time_patterns(self, offer_history) -> Dict[str, Any]:
        """Analyze user's response time patterns."""
        try:
            # This would analyze time patterns between offer views and clicks
            # For now, return placeholder data
            return {
                'avg_response_time_ms': 5000,  # 5 seconds average
                'peak_hours': [10, 14, 20],  # Peak activity hours
                'preferred_response_time': 'fast'
            }
            
        except Exception as e:
            logger.error(f"Error analyzing response time patterns: {e}")
            return {}
    
    def _generate_preference_vector(self, preference_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate preference vector from extracted data."""
        try:
            # This would use machine learning to generate preference vector
            # For now, create a simple weighted vector
            
            vector = {}
            
            # Category preferences (normalized)
            categories = preference_data.get('categories', {})
            total_category_views = sum(data['view_count'] for data in categories.values())
            
            for category, data in categories.items():
                if total_category_views > 0:
                    vector[f'category_{category}'] = {
                        'weight': data['view_count'] / total_category_views,
                        'avg_score': data['avg_score'],
                        'conversion_rate': data['conversion_count'] / max(1, data['view_count'])
                    }
            
            # Interest preferences (normalized)
            interests = preference_data.get('interests', {})
            total_interest_count = sum(interests.values())
            
            if total_interest_count > 0:
                for interest, count in interests.items():
                    vector[f'interest_{interest}'] = {
                        'weight': count / total_interest_count,
                        'frequency': count
                    }
            
            # Behavioral patterns
            behaviors = preference_data.get('behaviors', {})
            
            # Add behavioral features to vector
            if 'peak_activity_hours' in behaviors:
                for hour in behaviors['peak_activity_hours']:
                    vector[f'activity_hour_{hour}'] = {
                        'weight': 1.0,
                        'type': 'peak_hour'
                    }
            
            if 'preferred_price_range' in behaviors:
                price_range = behaviors['preferred_price_range']
                vector['price_preference'] = {
                    'range': price_range,
                    'weight': 0.5
                }
            
            if 'most_preferred' in behaviors:
                most_preferred = behaviors['most_preferred']
                vector['preferred_offer_type'] = {
                    'type': most_preferred,
                    'weight': 0.8
                }
            
            # Add metadata
            vector['metadata'] = {
                'created_at': timezone.now().isoformat(),
                'version': self._get_vector_version(),
                'data_points_count': preference_data.get('data_points_count', 0),
                'categories_count': preference_data.get('categories_count', 0),
                'interests_count': preference_data.get('interests_count', 0)
            }
            
            return vector
            
        except Exception as e:
            logger.error(f"Error generating preference vector: {e}")
            return {}
    
    def _get_vector_version(self) -> str:
        """Get current preference vector version."""
        return "1.0.0"
    
    def _update_preference_analytics(self, user: User, preference_vector: Dict[str, Any], preference_data: Dict[str, Any]):
        """Update analytics for preference vector changes."""
        try:
            # Log preference vector rebuild
            logger.info(f"Rebuilt preference vector for user {user.id} with {len(preference_vector)} features")
            
            # Update cache with new preference vector
            cache_key = f"preference_vector:{user.id}"
            self.cache_service.set(cache_key, preference_vector, PREFERENCE_VECTOR_CACHE_TIMEOUT)
            
        except Exception as e:
            logger.error(f"Error updating preference analytics for user {user.id}: {e}")
    
    def _update_preference_cache(self, user: User, preference_vector: Dict[str, Any]):
        """Update preference cache for user."""
        try:
            # Clear old preference cache entries
            cache_patterns = [
                f"preference_vector:{user.id}",
                f"user_preferences:{user.id}",
                f"user_affinity:{user.id}"
            ]
            
            for pattern in cache_patterns:
                # This would need pattern deletion support
                # For now, clear specific keys
                cache.delete(pattern)
            
            # Set new preference vector cache
            cache_key = f"preference_vector:{user.id}"
            self.cache_service.set(cache_key, preference_vector, PREFERENCE_VECTOR_CACHE_TIMEOUT)
            
        except Exception as e:
            logger.error(f"Error updating preference cache for user {user.id}: {e}")
    
    def _update_task_stats(self, start_time):
        """Update task execution statistics."""
        try:
            execution_time = (timezone.now() - start_time).total_seconds() * 1000
            
            self.task_stats['total_rebuilds'] += 1
            self.task_stats['successful_rebuilds'] += 1
            
            # Update average time
            current_avg = self.task_stats['avg_rebuild_time_ms']
            total_rebuilds = self.task_stats['total_rebuilds']
            self.task_stats['avg_rebuild_time_ms'] = (
                (current_avg * (total_rebuilds - 1) + execution_time) / total_rebuilds
            )
            
        except Exception as e:
            logger.error(f"Error updating task stats: {e}")
    
    def get_task_stats(self) -> Dict[str, Any]:
        """Get task execution statistics."""
        return self.task_stats
    
    def reset_task_stats(self) -> bool:
        """Reset task statistics."""
        try:
            self.task_stats = {
                'total_rebuilds': 0,
                'successful_rebuilds': 0,
                'failed_rebuilds': 0,
                'avg_rebuild_time_ms': 0.0
            }
            
            logger.info("Reset preference vector rebuild task statistics")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting task stats: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on preference vector rebuild task."""
        try:
            # Test context service
            context_health = self.context_service.health_check()
            
            # Test analytics service
            analytics_health = self.analytics_service.health_check()
            
            # Test cache functionality
            cache_health = self._test_cache_functionality()
            
            # Test preference vector generation
            test_user = User.objects.filter(is_active=True).first()
            if not test_user:
                test_user = User.objects.first()
            
            if test_user:
                test_history = UserOfferHistory.objects.filter(
                    user=test_user,
                    created_at__gte=timezone.now() - timezone.timedelta(days=30)
                )[:10]
                
                test_preference_data = self._extract_preference_data(test_user, test_history)
                test_vector = self._generate_preference_vector(test_preference_data)
                
                return {
                    'status': 'healthy' if all([
                        context_health.get('status') == 'healthy',
                        analytics_health.get('status') == 'healthy',
                        cache_health,
                        len(test_vector) > 0
                    ]) else 'unhealthy',
                    'context_service_health': context_health,
                    'analytics_service_health': analytics_health,
                    'cache_health': cache_health,
                    'preference_vector_test': len(test_vector) > 0,
                    'task_stats': self.task_stats,
                    'timestamp': timezone.now().isoformat()
                }
            
            return {
                'status': 'unhealthy',
                'error': 'No users available for testing',
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in preference vector rebuild task health check: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _test_cache_functionality(self) -> bool:
        """Test cache functionality."""
        try:
            # Test cache set and get
            test_key = "test_preference_vector_rebuild"
            test_value = {"test": True, "version": "1.0.0"}
            
            self.cache_service.set(test_key, test_value, 60)
            cached_value = self.cache_service.get(test_key)
            
            # Clean up
            self.cache_service.delete(test_key)
            
            return cached_value and cached_value.get('test') == test_value.get('test')
            
        except Exception as e:
            logger.error(f"Error testing cache functionality: {e}")
            return False


# Task instance
preference_vector_task = PreferenceVectorTask()
