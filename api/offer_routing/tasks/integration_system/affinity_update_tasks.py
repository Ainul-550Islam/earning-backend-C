"""
Affinity Update Tasks

Periodic tasks for updating user-category affinity
scores in the offer routing system.
"""

import logging
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.contrib.auth import get_user_model
from ..services.personalization import CollaborativeFilterService
from ..services.analytics import analytics_service
from ..services.cache import cache_service
from ..models import UserOfferHistory, OfferAffinityScore
from ..constants import AFFINITY_UPDATE_INTERVAL, AFFINITY_CACHE_TIMEOUT
from ..exceptions import PersonalizationError

logger = logging.getLogger(__name__)

User = get_user_model()


class AffinityUpdateTask:
    """
    Task for updating user-category affinity scores.
    
    Runs daily to recalculate:
    - User-category affinity scores
    - Category preferences
    - Interest profiles
    - Behavioral patterns
    - Collaborative filtering data
    """
    
    def __init__(self):
        self.collaborative_service = CollaborativeFilterService()
        self.analytics_service = analytics_service
        self.cache_service = cache_service
        self.task_stats = {
            'total_updates': 0,
            'successful_updates': 0,
            'failed_updates': 0,
            'avg_update_time_ms': 0.0
        }
    
    def run_affinity_update(self) -> Dict[str, Any]:
        """
        Run the affinity update task.
        
        Returns:
            Task execution results
        """
        try:
            start_time = timezone.now()
            
            # Get users that need affinity updates
            users_to_update = self._get_users_needing_update()
            
            if not users_to_update:
                logger.info("No users need affinity updates")
                return {
                    'success': True,
                    'message': 'No users need affinity updates',
                    'users_updated': 0,
                    'execution_time_ms': 0,
                    'timestamp': timezone.now().isoformat()
                }
            
            # Update affinity scores for each user
            updated_users = 0
            failed_users = 0
            
            for user in users_to_update:
                try:
                    # Update user affinity
                    result = self._update_user_affinity(user)
                    
                    if result['success']:
                        updated_users += 1
                        logger.info(f"Updated affinity for user {user.id}")
                    else:
                        failed_users += 1
                        logger.error(f"Failed to update affinity for user {user.id}: {result['error']}")
                        
                except Exception as e:
                    failed_users += 1
                    logger.error(f"Error updating affinity for user {user.id}: {e}")
            
            # Update task statistics
            self._update_task_stats(start_time)
            
            # Clear relevant cache
            self._clear_affinity_cache(users_to_update)
            
            return {
                'success': True,
                'message': 'Affinity update task completed',
                'users_updated': updated_users,
                'users_failed': failed_users,
                'total_users': len(users_to_update),
                'execution_time_ms': (timezone.now() - start_time).total_seconds() * 1000,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in affinity update task: {e}")
            return {
                'success': False,
                'error': str(e),
                'execution_time_ms': 0,
                'timestamp': timezone.now().isoformat()
            }
    
    def _get_users_needing_update(self) -> List[User]:
        """Get users that need affinity updates."""
        try:
            # Get users with recent activity
            cutoff_time = timezone.now() - timezone.timedelta(days=AFFINITY_UPDATE_INTERVAL)
            
            users = User.objects.filter(
                is_active=True,
                last_login__gte=cutoff_time
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
            logger.error(f"Error getting users needing affinity update: {e}")
            return []
    
    def _update_user_affinity(self, user: User) -> Dict[str, Any]:
        """Update affinity scores for a specific user."""
        try:
            # Get current affinity scores
            current_affinity = OfferAffinityScore.objects.filter(user=user)
            
            # Calculate new affinity scores
            new_affinity_scores = self._calculate_affinity_scores(user)
            
            # Update or create affinity records
            updated_scores = 0
            with transaction.atomic():
                for category, score_data in new_affinity_scores.items():
                    # Update existing record or create new one
                    affinity_record, created = OfferAffinityScore.objects.update_or_create(
                        user=user,
                        category=category,
                        defaults={
                            'affinity_score': score_data['score'],
                            'confidence': score_data['confidence'],
                            'sample_size': score_data['sample_size'],
                            'last_updated': timezone.now()
                        }
                    )
                    
                    if not created:
                        # Update existing record
                        affinity_record.affinity_score = score_data['score']
                        affinity_record.confidence = score_data['confidence']
                        affinity_record.sample_size = score_data['sample_size']
                        affinity_record.last_updated = timezone.now()
                        affinity_record.save()
                    
                    updated_scores += 1
            
            # Update user's preference vector
            self._update_preference_vector(user, new_affinity_scores)
            
            # Update analytics
            self._update_affinity_analytics(user, new_affinity_scores)
            
            return {
                'success': True,
                'user_id': user.id,
                'previous_scores': len(current_affinity),
                'updated_scores': updated_scores,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error updating affinity for user {user.id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'user_id': user.id,
                'timestamp': timezone.now().isoformat()
            }
    
    def _calculate_affinity_scores(self, user: User) -> Dict[str, Any]:
        """Calculate affinity scores for a user."""
        try:
            # Get user's offer history
            offer_history = UserOfferHistory.objects.filter(
                user=user,
                created_at__gte=timezone.now() - timezone.timedelta(days=90)
            ).order_by('-created_at')
            
            # Calculate category affinity
            category_affinity = self._calculate_category_affinity(offer_history)
            
            # Calculate collaborative filtering scores
            collaborative_scores = self._calculate_collaborative_scores(user, offer_history)
            
            # Combine scores
            combined_scores = {}
            
            for category in category_affinity.keys():
                category_score = category_affinity[category]['score']
                collaborative_score = collaborative_scores.get(category, 0.0)
                
                # Weighted combination
                combined_score = (
                    category_score * 0.7 +  # 70% weight to category affinity
                    collaborative_score * 0.3    # 30% weight to collaborative filtering
                )
                
                combined_scores[category] = {
                    'score': combined_score,
                    'confidence': min(0.95, category_affinity[category]['confidence']),
                    'sample_size': category_affinity[category]['sample_size'],
                    'category_score': category_score,
                    'collaborative_score': collaborative_score
                }
            
            return combined_scores
            
        except Exception as e:
            logger.error(f"Error calculating affinity scores for user {user.id}: {e}")
            return {}
    
    def _calculate_category_affinity(self, offer_history) -> Dict[str, Any]:
        """Calculate category affinity from offer history."""
        try:
            category_scores = {}
            
            # Group offers by category
            category_data = {}
            for history_item in offer_history:
                category = history_item.offer.category or 'general'
                
                if category not in category_data:
                    category_data[category] = []
                
                category_data[category].append({
                    'clicked': history_item.clicked_at is not None,
                    'converted': history_item.completed_at is not None,
                    'score': history_item.score_at_time or 0.0,
                    'created_at': history_item.created_at
                })
            
            # Calculate affinity scores for each category
            for category, items in category_data.items():
                if not items:
                    continue
                
                total_items = len(items)
                clicked_items = sum(1 for item in items if item['clicked'])
                converted_items = sum(1 for item in items if item['converted'])
                avg_score = sum(item['score'] for item in items) / total_items if total_items > 0 else 0.0
                
                # Calculate affinity score
                click_rate = clicked_items / total_items if total_items > 0 else 0.0
                conversion_rate = converted_items / total_items if total_items > 0 else 0.0
                
                # Higher score for recent activity
                recency_weight = 1.0
                if items:
                    most_recent = max(item['created_at'] for item in items)
                    days_since_recent = (timezone.now() - most_recent).days
                    recency_weight = max(0.1, 1.0 - (days_since_recent / 30.0))
                
                affinity_score = (
                    avg_score * 0.4 +                    # 40% weight to average score
                    click_rate * 0.3 +                   # 30% weight to click rate
                    conversion_rate * 0.2 +                 # 20% weight to conversion rate
                    recency_weight * 0.1                     # 10% weight to recency
                )
                
                # Calculate confidence based on sample size
                confidence = min(0.95, total_items / 50.0)  # More confidence with larger samples
                
                category_scores[category] = {
                    'score': affinity_score,
                    'confidence': confidence,
                    'sample_size': total_items,
                    'click_rate': click_rate,
                    'conversion_rate': conversion_rate,
                    'avg_score': avg_score
                }
            
            return category_scores
            
        except Exception as e:
            logger.error(f"Error calculating category affinity: {e}")
            return {}
    
    def _calculate_collaborative_scores(self, user: User, offer_history) -> Dict[str, Any]:
        """Calculate collaborative filtering scores."""
        try:
            collaborative_scores = {}
            
            # Get similar users
            similar_users = self.collaborative_service.get_similar_users(user, limit=20)
            
            # Get offers viewed by similar users
            similar_user_ids = [similar_user.id for similar_user in similar_users]
            similar_offers = UserOfferHistory.objects.filter(
                user_id__in=similar_user_ids,
                created_at__gte=timezone.now() - timezone.timedelta(days=30)
            ).values_list('offer_id', 'score_at_time').distinct()
            
            # Group similar offers by category
            category_data = {}
            for offer_data in similar_offers:
                offer_id = offer_data['offer_id']
                score = offer_data['score_at_time'] or 0.0
                
                # Get offer details (would need to query OfferRoute model)
                # For now, use placeholder category
                category = 'general'  # This would be fetched from OfferRoute
                
                if category not in category_data:
                    category_data[category] = []
                
                category_data[category].append({
                    'offer_id': offer_id,
                    'score': score,
                    'weight': 1.0  # Equal weight for similar users
                })
            
            # Calculate collaborative scores for each category
            for category, offers in category_data.items():
                if not offers:
                    continue
                
                # Calculate weighted average score
                total_weight = sum(offer['weight'] for offer in offers)
                if total_weight == 0:
                    continue
                
                weighted_score = sum(offer['score'] * offer['weight'] for offer in offers) / total_weight
                
                collaborative_scores[category] = {
                    'score': weighted_score,
                    'sample_size': len(offers),
                    'similar_users': len(similar_users)
                }
            
            return collaborative_scores
            
        except Exception as e:
            logger.error(f"Error calculating collaborative scores for user {user.id}: {e}")
            return {}
    
    def _update_preference_vector(self, user: User, affinity_scores: Dict[str, Any]):
        """Update user's preference vector."""
        try:
            # This would update the user's preference vector model
            # For now, just log the update
            logger.info(f"Updating preference vector for user {user.id} with {len(affinity_scores)} category scores")
            
            # Update cache with new preference vector
            cache_key = f"preference_vector:{user.id}"
            preference_data = {
                'user_id': user.id,
                'category_affinity': affinity_scores,
                'updated_at': timezone.now().isoformat(),
                'version': '1.0'
            }
            
            self.cache_service.set(cache_key, preference_data, AFFINITY_CACHE_TIMEOUT)
            
        except Exception as e:
            logger.error(f"Error updating preference vector for user {user.id}: {e}")
    
    def _update_affinity_analytics(self, user: User, affinity_scores: Dict[str, Any]):
        """Update analytics for affinity changes."""
        try:
            # Log affinity update
            logger.info(f"Updated affinity for user {user.id}: {len(affinity_scores)} categories")
            
            # Update cache with new affinity scores
            for category, score_data in affinity_scores.items():
                cache_key = f"affinity_score:{user.id}:{category}"
                self.cache_service.set(cache_key, score_data, AFFINITY_CACHE_TIMEOUT)
            
        except Exception as e:
            logger.error(f"Error updating affinity analytics for user {user.id}: {e}")
    
    def _clear_affinity_cache(self, users: List[User]):
        """Clear affinity cache for updated users."""
        try:
            for user in users:
                # Clear user-specific cache entries
                cache_patterns = [
                    f"affinity_score:{user.id}:*",
                    f"preference_vector:{user.id}",
                    f"user_affinity:{user.id}"
                ]
                
                for pattern in cache_patterns:
                    # This would need pattern deletion support
                    # For now, clear specific keys
                    cache.delete(f"affinity_score:{user.id}:general")
                    cache.delete(f"preference_vector:{user.id}")
            
        except Exception as e:
            logger.error(f"Error clearing affinity cache: {e}")
    
    def _update_task_stats(self, start_time):
        """Update task execution statistics."""
        try:
            execution_time = (timezone.now() - start_time).total_seconds() * 1000
            
            self.task_stats['total_updates'] += 1
            self.task_stats['successful_updates'] += 1
            
            # Update average time
            current_avg = self.task_stats['avg_update_time_ms']
            total_updates = self.task_stats['total_updates']
            self.task_stats['avg_update_time_ms'] = (
                (current_avg * (total_updates - 1) + execution_time) / total_updates
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
                'total_updates': 0,
                'successful_updates': 0,
                'failed_updates': 0,
                'avg_update_time_ms': 0.0
            }
            
            logger.info("Reset affinity update task statistics")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting task stats: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on affinity update task."""
        try:
            # Test collaborative service
            collab_health = self.collaborative_service.health_check()
            
            # Test analytics service
            analytics_health = self.analytics_service.health_check()
            
            # Test cache functionality
            cache_health = self._test_cache_functionality()
            
            # Test affinity calculation
            test_user = User.objects.filter(is_active=True).first()
            if not test_user:
                test_user = User.objects.first()
            
            if test_user:
                test_result = self._update_user_affinity(test_user)
                
                return {
                    'status': 'healthy' if all([
                        collab_health.get('status') == 'healthy',
                        analytics_health.get('status') == 'healthy',
                        cache_health,
                        test_result['success']
                    ]) else 'unhealthy',
                    'collaborative_service_health': collab_health,
                    'analytics_service_health': analytics_health,
                    'cache_health': cache_health,
                    'affinity_test': test_result,
                    'task_stats': self.task_stats,
                    'timestamp': timezone.now().isoformat()
                }
            
            return {
                'status': 'unhealthy',
                'error': 'No users available for testing',
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in affinity update task health check: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _test_cache_functionality(self) -> bool:
        """Test cache functionality."""
        try:
            # Test cache set and get
            test_key = "test_affinity_update"
            test_value = {"test": True, "score": 0.75}
            
            self.cache_service.set(test_key, test_value, 60)
            cached_value = self.cache_service.get(test_key)
            
            # Clean up
            self.cache_service.delete(test_key)
            
            return cached_value and cached_value.get('test') == test_value.get('test')
            
        except Exception as e:
            logger.error(f"Error testing cache functionality: {e}")
            return False


# Task instance
affinity_update_task = AffinityUpdateTask()
