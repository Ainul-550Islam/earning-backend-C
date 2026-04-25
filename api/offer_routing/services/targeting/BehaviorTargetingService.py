"""
Behavior Targeting Service

Handles behavior event matching for behavior-based
targeting rules in offer routing system.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum
from django.core.cache import cache
from ....models import (
    OfferRoute, BehaviorRouteRule, RoutingDecisionLog,
    UserOfferHistory, RoutingDecisionLog
)
from ....choices import EventType
from ....constants import (
    BEHAVIOR_CACHE_TIMEOUT, EVENT_CACHE_TIMEOUT,
    MAX_BEHAVIOR_LOOKUPS_PER_SECOND, BEHAVIOR_PARSE_TIMEOUT,
    DEFAULT_BEHAVIOR_WINDOW_DAYS, MIN_BEHAVIOR_SAMPLE_SIZE
)
from ....exceptions import TargetingError, BehaviorParsingError
from ....utils import get_user_behavior_data, calculate_behavior_score

User = get_user_model()
logger = logging.getLogger(__name__)


class BehaviorTargetingService:
    """
    Service for behavior-based targeting rules.
    
    Provides behavior event tracking and matching against
    behavior-based targeting rules for offer routing.
    
    Performance targets:
    - Behavior lookup: <20ms (cached), <100ms (uncached)
    - Rule matching: <5ms per rule
    - Cache hit rate: >90%
    """
    
    def __init__(self):
        self.cache_service = cache
        self.behavior_stats = {
            'total_lookups': 0,
            'cache_hits': 0,
            'errors': 0,
            'avg_lookup_time_ms': 0.0
        }
        self.rate_limiter = {
            'lookups': [],
            'window_start': timezone.now()
        }
        
        # Behavior event definitions
        self._initialize_behavior_definitions()
    
    def _initialize_behavior_definitions(self):
        """Initialize behavior event definitions and weights."""
        self.behavior_events = {
            'offer_view': {
                'name': 'Offer View',
                'description': 'User viewed an offer',
                'weight': 1.0,
                'category': 'engagement',
                'default_window_days': 30
            },
            'offer_click': {
                'name': 'Offer Click',
                'description': 'User clicked on an offer',
                'weight': 3.0,
                'category': 'engagement',
                'default_window_days': 30
            },
            'offer_conversion': {
                'name': 'Offer Conversion',
                'description': 'User completed an offer conversion',
                'weight': 10.0,
                'category': 'conversion',
                'default_window_days': 90
            },
            'page_view': {
                'name': 'Page View',
                'description': 'User viewed a page',
                'weight': 0.5,
                'category': 'engagement',
                'default_window_days': 7
            },
            'session_start': {
                'name': 'Session Start',
                'description': 'User started a session',
                'weight': 0.2,
                'category': 'activity',
                'default_window_days': 7
            },
            'session_end': {
                'name': 'Session End',
                'description': 'User ended a session',
                'weight': 0.2,
                'category': 'activity',
                'default_window_days': 7
            },
            'add_to_wishlist': {
                'name': 'Add to Wishlist',
                'description': 'User added offer to wishlist',
                'weight': 5.0,
                'category': 'engagement',
                'default_window_days': 60
            },
            'search_query': {
                'name': 'Search Query',
                'description': 'User performed a search',
                'weight': 1.5,
                'category': 'intent',
                'default_window_days': 14
            },
            'category_browse': {
                'name': 'Category Browse',
                'description': 'User browsed a category',
                'weight': 2.0,
                'category': 'intent',
                'default_window_days': 21
            },
            'email_open': {
                'name': 'Email Open',
                'description': 'User opened an email',
                'weight': 2.5,
                'category': 'engagement',
                'default_window_days': 30
            },
            'email_click': {
                'name': 'Email Click',
                'description': 'User clicked an email link',
                'weight': 4.0,
                'category': 'engagement',
                'default_window_days': 30
            },
            'social_share': {
                'name': 'Social Share',
                'description': 'User shared content on social media',
                'weight': 6.0,
                'category': 'engagement',
                'default_window_days': 45
            },
            'review_submission': {
                'name': 'Review Submission',
                'description': 'User submitted a review',
                'weight': 4.0,
                'category': 'engagement',
                'default_window_days': 90
            },
            'support_contact': {
                'name': 'Support Contact',
                'description': 'User contacted support',
                'weight': 1.0,
                'category': 'support',
                'default_window_days': 30
            },
            'purchase': {
                'name': 'Purchase',
                'description': 'User made a purchase',
                'weight': 15.0,
                'category': 'conversion',
                'default_window_days': 180
            },
            'cart_addition': {
                'name': 'Cart Addition',
                'description': 'User added item to cart',
                'weight': 3.5,
                'category': 'intent',
                'default_window_days': 14
            },
            'cart_abandonment': {
                'name': 'Cart Abandonment',
                'description': 'User abandoned cart',
                'weight': 2.0,
                'category': 'intent',
                'default_window_days': 7
            }
        }
        
        # Behavior patterns for complex targeting
        self.behavior_patterns = {
            'high_engagement': {
                'name': 'High Engagement',
                'description': 'User shows high engagement patterns',
                'criteria': {
                    'offer_clicks': {'min': 5, 'window_days': 7},
                    'session_duration': {'min': 300, 'window_days': 7},  # 5 minutes
                    'page_views_per_session': {'min': 5, 'window_days': 7}
                },
                'weight': 2.0
            },
            'frequent_converter': {
                'name': 'Frequent Converter',
                'description': 'User converts frequently',
                'criteria': {
                    'offer_conversions': {'min': 2, 'window_days': 30},
                    'conversion_rate': {'min': 0.05, 'window_days': 30}
                },
                'weight': 3.0
            },
            'price_sensitive': {
                'name': 'Price Sensitive',
                'description': 'User shows price-sensitive behavior',
                'criteria': {
                    'price_comparison_searches': {'min': 3, 'window_days': 14},
                    'discount_usage': {'min': 2, 'window_days': 30},
                    'cart_abandonment_rate': {'min': 0.5, 'window_days': 30}
                },
                'weight': 1.5
            },
            'brand_loyal': {
                'name': 'Brand Loyal',
                'description': 'User shows brand loyalty patterns',
                'criteria': {
                    'repeat_purchases': {'min': 3, 'window_days': 90},
                    'single_brand_purchases': {'min': 0.8, 'window_days': 90},
                    'low_return_rate': {'max': 0.1, 'window_days': 90}
                },
                'weight': 2.5
            },
            'explorer': {
                'name': 'Explorer',
                'description': 'User explores many categories',
                'criteria': {
                    'unique_categories_viewed': {'min': 10, 'window_days': 30},
                    'category_diversity': {'min': 0.7, 'window_days': 30},
                    'low_repeat_category_rate': {'max': 0.3, 'window_days': 30}
                },
                'weight': 1.8
            },
            'at_risk': {
                'name': 'At Risk',
                'description': 'User shows churn risk patterns',
                'criteria': {
                    'decreasing_activity': {'min': 0.5, 'window_days': 14},
                    'increasing_cart_abandonment': {'min': 0.3, 'window_days': 14},
                    'low_recent_conversions': {'max': 1, 'window_days': 30}
                },
                'weight': 1.2
            }
        }
    
    def matches_route(self, route: OfferRoute, user: User, 
                     context: Dict[str, Any]) -> bool:
        """
        Check if route matches user's behavior patterns.
        
        Args:
            route: Route to check
            user: User object
            context: User context
            
        Returns:
            True if route matches behavior-wise, False otherwise
        """
        try:
            # Get behavior rules for route
            behavior_rules = route.behavior_rules.filter(is_active=True).order_by('priority')
            
            if not behavior_rules:
                return True  # No behavior restrictions
            
            # Get user's behavior data
            user_behavior = self._get_user_behavior_data(user, context)
            
            if not user_behavior:
                logger.warning(f"Could not determine behavior for user {user.id}")
                return False  # Cannot apply behavior targeting without behavior data
            
            # Check each behavior rule
            for rule in behavior_rules:
                if self._matches_behavior_rule(rule, user_behavior):
                    return True  # Behavior rule matches
            
            # If no rules matched, return False
            return False
            
        except Exception as e:
            logger.error(f"Error checking behavior targeting for route {route.id}: {e}")
            return False
    
    def _get_user_behavior_data(self, user: User, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get user's behavior data with caching."""
        try:
            # Check cache first
            cache_key = f"user_behavior:{user.id}"
            cached_behavior = self.cache_service.get(cache_key)
            
            if cached_behavior:
                self.behavior_stats['cache_hits'] += 1
                return cached_behavior
            
            start_time = timezone.now()
            
            # Calculate user behavior data
            behavior_data = {
                'events': self._get_user_events(user),
                'patterns': self._get_user_patterns(user),
                'metrics': self._get_user_metrics(user),
                'calculated_at': timezone.now().isoformat()
            }
            
            # Cache result
            self.cache_service.set(cache_key, behavior_data, BEHAVIOR_CACHE_TIMEOUT)
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_behavior_stats(elapsed_ms)
            
            return behavior_data
            
        except Exception as e:
            logger.error(f"Error getting user behavior data for {user.id}: {e}")
            self.behavior_stats['errors'] += 1
            return None
    
    def _get_user_events(self, user: User) -> Dict[str, Any]:
        """Get user's behavior events."""
        try:
            events = {}
            
            # Get events from different sources
            event_sources = [
                self._get_offer_history_events(user),
                self._get_routing_decision_events(user),
                self._get_analytics_events(user)
            ]
            
            # Combine events
            all_events = []
            for source_events in event_sources:
                all_events.extend(source_events)
            
            # Group events by type
            for event in all_events:
                event_type = event.get('event_type', 'unknown')
                if event_type not in events:
                    events[event_type] = {
                        'count': 0,
                        'recent_events': [],
                        'total_weight': 0.0,
                        'first_seen': None,
                        'last_seen': None
                    }
                
                events[event_type]['count'] += 1
                
                # Add weight
                event_weight = self.behavior_events.get(event_type, {}).get('weight', 1.0)
                events[event_type]['total_weight'] += event_weight
                
                # Track recent events
                if len(events[event_type]['recent_events']) < 10:
                    events[event_type]['recent_events'].append(event)
                
                # Track first and last seen
                event_time = event.get('created_at')
                if event_time:
                    if not events[event_type]['first_seen'] or event_time < events[event_type]['first_seen']:
                        events[event_type]['first_seen'] = event_time
                    
                    if not events[event_type]['last_seen'] or event_time > events[event_type]['last_seen']:
                        events[event_type]['last_seen'] = event_time
            
            return events
            
        except Exception as e:
            logger.error(f"Error getting user events: {e}")
            return {}
    
    def _get_offer_history_events(self, user: User) -> List[Dict[str, Any]]:
        """Get events from offer history."""
        try:
            history_events = UserOfferHistory.objects.filter(user=user).order_by('-created_at')[:1000]
            
            events = []
            for history in history_events:
                event_data = {
                    'event_type': 'offer_view',
                    'created_at': history.viewed_at,
                    'offer_id': history.offer_id,
                    'route_id': history.route_id,
                    'score_at_time': float(history.score_at_time or 0),
                    'decision_reason': history.decision_reason
                }
                
                if history.clicked_at:
                    events.append({
                        'event_type': 'offer_click',
                        'created_at': history.clicked_at,
                        'offer_id': history.offer_id,
                        'route_id': history.route_id
                    })
                
                if history.completed_at:
                    events.append({
                        'event_type': 'offer_conversion',
                        'created_at': history.completed_at,
                        'offer_id': history.offer_id,
                        'route_id': history.route_id,
                        'conversion_value': float(history.conversion_value or 0)
                    })
                
                events.append(event_data)
            
            return events
            
        except Exception as e:
            logger.error(f"Error getting offer history events: {e}")
            return []
    
    def _get_routing_decision_events(self, user: User) -> List[Dict[str, Any]]:
        """Get events from routing decisions."""
        try:
            decision_events = RoutingDecisionLog.objects.filter(user=user).order_by('-created_at')[:500]
            
            events = []
            for decision in decision_events:
                events.append({
                    'event_type': 'routing_decision',
                    'created_at': decision.created_at,
                    'offer_id': decision.offer_id,
                    'route_id': decision.route_id,
                    'score': float(decision.score or 0),
                    'reason': decision.reason,
                    'response_time_ms': decision.response_time_ms,
                    'cache_hit': decision.cache_hit,
                    'personalization_applied': decision.personalization_applied
                })
            
            return events
            
        except Exception as e:
            logger.error(f"Error getting routing decision events: {e}")
            return []
    
    def _get_analytics_events(self, user: User) -> List[Dict[str, Any]]:
        """Get events from analytics system."""
        try:
            # This would integrate with an analytics system
            # For now, return empty list
            return []
            
        except Exception as e:
            logger.error(f"Error getting analytics events: {e}")
            return []
    
    def _get_user_patterns(self, user: User) -> Dict[str, Any]:
        """Get user's behavior patterns."""
        try:
            patterns = {}
            
            # Calculate each behavior pattern
            for pattern_name, pattern_def in self.behavior_patterns.items():
                pattern_result = self._calculate_behavior_pattern(user, pattern_name, pattern_def)
                
                if pattern_result['matches']:
                    patterns[pattern_name] = {
                        'name': pattern_def['name'],
                        'description': pattern_def['description'],
                        'weight': pattern_def['weight'],
                        'confidence': pattern_result['confidence'],
                        'criteria_scores': pattern_result['criteria_scores'],
                        'calculated_at': timezone.now().isoformat()
                    }
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error getting user patterns: {e}")
            return {}
    
    def _calculate_behavior_pattern(self, user: User, pattern_name: str, 
                                pattern_def: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate if user matches a specific behavior pattern."""
        try:
            criteria = pattern_def['criteria']
            criteria_scores = {}
            total_score = 0.0
            criteria_count = len(criteria)
            
            # Evaluate each criterion
            for criterion_name, criterion_config in criteria.items():
                score = self._evaluate_behavior_criterion(user, criterion_name, criterion_config)
                criteria_scores[criterion_name] = score
                total_score += score
            
            # Calculate average score as confidence
            confidence = total_score / criteria_count if criteria_count > 0 else 0.0
            
            # Determine if user matches pattern
            matches = confidence >= 0.5  # 50% threshold
            
            return {
                'matches': matches,
                'confidence': confidence,
                'criteria_scores': criteria_scores,
                'total_score': total_score
            }
            
        except Exception as e:
            logger.error(f"Error calculating pattern {pattern_name}: {e}")
            return {
                'matches': False,
                'confidence': 0.0,
                'criteria_scores': {},
                'total_score': 0.0
            }
    
    def _evaluate_behavior_criterion(self, user: User, criterion_name: str, 
                                   criterion_config: Dict[str, Any]) -> float:
        """Evaluate a single behavior criterion."""
        try:
            if criterion_name == 'offer_clicks':
                return self._evaluate_offer_clicks(user, criterion_config)
            elif criterion_name == 'session_duration':
                return self._evaluate_session_duration(user, criterion_config)
            elif criterion_name == 'page_views_per_session':
                return self._evaluate_page_views_per_session(user, criterion_config)
            elif criterion_name == 'offer_conversions':
                return self._evaluate_offer_conversions(user, criterion_config)
            elif criterion_name == 'conversion_rate':
                return self._evaluate_conversion_rate(user, criterion_config)
            elif criterion_name == 'price_comparison_searches':
                return self._evaluate_price_comparison_searches(user, criterion_config)
            elif criterion_name == 'discount_usage':
                return self._evaluate_discount_usage(user, criterion_config)
            elif criterion_name == 'cart_abandonment_rate':
                return self._evaluate_cart_abandonment_rate(user, criterion_config)
            elif criterion_name == 'repeat_purchases':
                return self._evaluate_repeat_purchases(user, criterion_config)
            elif criterion_name == 'single_brand_purchases':
                return self._evaluate_single_brand_purchases(user, criterion_config)
            elif criterion_name == 'low_return_rate':
                return self._evaluate_low_return_rate(user, criterion_config)
            elif criterion_name == 'unique_categories_viewed':
                return self._evaluate_unique_categories_viewed(user, criterion_config)
            elif criterion_name == 'category_diversity':
                return self._evaluate_category_diversity(user, criterion_config)
            elif criterion_name == 'low_repeat_category_rate':
                return self._evaluate_low_repeat_category_rate(user, criterion_config)
            elif criterion_name == 'decreasing_activity':
                return self._evaluate_decreasing_activity(user, criterion_config)
            elif criterion_name == 'increasing_cart_abandonment':
                return self._evaluate_increasing_cart_abandonment(user, criterion_config)
            elif criterion_name == 'low_recent_conversions':
                return self._evaluate_low_recent_conversions(user, criterion_config)
            else:
                logger.warning(f"Unknown behavior criterion: {criterion_name}")
                return 0.0
                
        except Exception as e:
            logger.error(f"Error evaluating behavior criterion {criterion_name}: {e}")
            return 0.0
    
    def _evaluate_offer_clicks(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate offer clicks criterion."""
        try:
            window_days = criterion_config.get('window_days', 7)
            min_clicks = criterion_config.get('min', 5)
            
            cutoff_date = timezone.now() - timezone.timedelta(days=window_days)
            
            click_count = UserOfferHistory.objects.filter(
                user=user,
                clicked_at__gte=cutoff_date
            ).count()
            
            if click_count >= min_clicks:
                return 1.0
            else:
                return max(0.0, click_count / min_clicks)
                
        except Exception as e:
            logger.error(f"Error evaluating offer clicks: {e}")
            return 0.0
    
    def _evaluate_session_duration(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate session duration criterion."""
        try:
            window_days = criterion_config.get('window_days', 7)
            min_duration = criterion_config.get('min', 300)  # 5 minutes
            
            cutoff_date = timezone.now() - timezone.timedelta(days=window_days)
            
            # This would come from analytics system
            # For now, return a reasonable estimate
            avg_duration = 420  # 7 minutes average
            
            if avg_duration >= min_duration:
                return 1.0
            else:
                return max(0.0, avg_duration / min_duration)
                
        except Exception as e:
            logger.error(f"Error evaluating session duration: {e}")
            return 0.0
    
    def _evaluate_page_views_per_session(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate page views per session criterion."""
        try:
            window_days = criterion_config.get('window_days', 7)
            min_views = criterion_config.get('min', 5)
            
            cutoff_date = timezone.now() - timezone.timedelta(days=window_days)
            
            # This would come from analytics system
            # For now, return a reasonable estimate
            avg_views = 6.2  # Average page views per session
            
            if avg_views >= min_views:
                return 1.0
            else:
                return max(0.0, avg_views / min_views)
                
        except Exception as e:
            logger.error(f"Error evaluating page views per session: {e}")
            return 0.0
    
    def _evaluate_offer_conversions(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate offer conversions criterion."""
        try:
            window_days = criterion_config.get('window_days', 30)
            min_conversions = criterion_config.get('min', 2)
            
            cutoff_date = timezone.now() - timezone.timedelta(days=window_days)
            
            conversion_count = UserOfferHistory.objects.filter(
                user=user,
                completed_at__gte=cutoff_date
            ).count()
            
            if conversion_count >= min_conversions:
                return 1.0
            else:
                return max(0.0, conversion_count / min_conversions)
                
        except Exception as e:
            logger.error(f"Error evaluating offer conversions: {e}")
            return 0.0
    
    def _evaluate_conversion_rate(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate conversion rate criterion."""
        try:
            window_days = criterion_config.get('window_days', 30)
            min_rate = criterion_config.get('min', 0.05)
            
            cutoff_date = timezone.now() - timezone.timedelta(days=window_days)
            
            views_count = UserOfferHistory.objects.filter(
                user=user,
                viewed_at__gte=cutoff_date
            ).count()
            
            conversions_count = UserOfferHistory.objects.filter(
                user=user,
                completed_at__gte=cutoff_date
            ).count()
            
            if views_count == 0:
                return 0.0
            
            conversion_rate = conversions_count / views_count
            
            if conversion_rate >= min_rate:
                return 1.0
            else:
                return max(0.0, conversion_rate / min_rate)
                
        except Exception as e:
            logger.error(f"Error evaluating conversion rate: {e}")
            return 0.0
    
    def _evaluate_price_comparison_searches(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate price comparison searches criterion."""
        try:
            window_days = criterion_config.get('window_days', 14)
            min_searches = criterion_config.get('min', 3)
            
            # This would come from analytics system
            # For now, return a reasonable estimate
            price_searches = 2.1  # Average price comparison searches
            
            if price_searches >= min_searches:
                return 1.0
            else:
                return max(0.0, price_searches / min_searches)
                
        except Exception as e:
            logger.error(f"Error evaluating price comparison searches: {e}")
            return 0.0
    
    def _evaluate_discount_usage(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate discount usage criterion."""
        try:
            window_days = criterion_config.get('window_days', 30)
            min_usage = criterion_config.get('min', 2)
            
            # This would come from analytics/e-commerce system
            # For now, return a reasonable estimate
            discount_usage = 1.8  # Average discount usage
            
            if discount_usage >= min_usage:
                return 1.0
            else:
                return max(0.0, discount_usage / min_usage)
                
        except Exception as e:
            logger.error(f"Error evaluating discount usage: {e}")
            return 0.0
    
    def _evaluate_cart_abandonment_rate(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate cart abandonment rate criterion."""
        try:
            window_days = criterion_config.get('window_days', 30)
            max_rate = criterion_config.get('max', 0.5)
            
            # This would come from analytics/e-commerce system
            # For now, return a reasonable estimate
            abandonment_rate = 0.35  # 35% cart abandonment rate
            
            if abandonment_rate <= max_rate:
                return 1.0
            else:
                return max(0.0, 1.0 - (abandonment_rate - max_rate))
                
        except Exception as e:
            logger.error(f"Error evaluating cart abandonment rate: {e}")
            return 0.0
    
    def _evaluate_repeat_purchases(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate repeat purchases criterion."""
        try:
            window_days = criterion_config.get('window_days', 90)
            min_purchases = criterion_config.get('min', 3)
            
            # This would come from e-commerce system
            # For now, return a reasonable estimate
            repeat_purchases = 2.3  # Average repeat purchases
            
            if repeat_purchases >= min_purchases:
                return 1.0
            else:
                return max(0.0, repeat_purchases / min_purchases)
                
        except Exception as e:
            logger.error(f"Error evaluating repeat purchases: {e}")
            return 0.0
    
    def _evaluate_single_brand_purchases(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate single brand purchases criterion."""
        try:
            window_days = criterion_config.get('window_days', 90)
            min_ratio = criterion_config.get('min', 0.8)
            
            # This would come from e-commerce system
            # For now, return a reasonable estimate
            single_brand_ratio = 0.65  # 65% single brand purchases
            
            if single_brand_ratio >= min_ratio:
                return 1.0
            else:
                return max(0.0, single_brand_ratio / min_ratio)
                
        except Exception as e:
            logger.error(f"Error evaluating single brand purchases: {e}")
            return 0.0
    
    def _evaluate_low_return_rate(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate low return rate criterion."""
        try:
            window_days = criterion_config.get('window_days', 90)
            max_rate = criterion_config.get('max', 0.1)
            
            # This would come from e-commerce system
            # For now, return a reasonable estimate
            return_rate = 0.08  # 8% return rate
            
            if return_rate <= max_rate:
                return 1.0
            else:
                return max(0.0, 1.0 - (return_rate - max_rate))
                
        except Exception as e:
            logger.error(f"Error evaluating low return rate: {e}")
            return 0.0
    
    def _evaluate_unique_categories_viewed(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate unique categories viewed criterion."""
        try:
            window_days = criterion_config.get('window_days', 30)
            min_categories = criterion_config.get('min', 10)
            
            cutoff_date = timezone.now() - timezone.timedelta(days=window_days)
            
            # Get unique categories from offer history
            unique_categories = UserOfferHistory.objects.filter(
                user=user,
                viewed_at__gte=cutoff_date
            ).values('offer__category').distinct().count()
            
            if unique_categories >= min_categories:
                return 1.0
            else:
                return max(0.0, unique_categories / min_categories)
                
        except Exception as e:
            logger.error(f"Error evaluating unique categories viewed: {e}")
            return 0.0
    
    def _evaluate_category_diversity(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate category diversity criterion."""
        try:
            window_days = criterion_config.get('window_days', 30)
            min_diversity = criterion_config.get('min', 0.7)
            
            cutoff_date = timezone.now() - timezone.timedelta(days=window_days)
            
            # Calculate category diversity
            category_views = UserOfferHistory.objects.filter(
                user=user,
                viewed_at__gte=cutoff_date
            ).values('offer__category').annotate(
                view_count=Count('id')
            ).order_by('-view_count')
            
            if not category_views:
                return 0.0
            
            total_views = sum(item['view_count'] for item in category_views)
            
            # Calculate Shannon entropy for diversity
            entropy = 0.0
            for category_data in category_views:
                probability = category_data['view_count'] / total_views
                if probability > 0:
                    entropy -= probability * (probability.bit_length() - 1)  # log2 approximation
            
            # Normalize entropy (max entropy is log2 of number of categories)
            max_entropy = len(category_views).bit_length() - 1
            diversity = entropy / max_entropy if max_entropy > 0 else 0.0
            
            if diversity >= min_diversity:
                return 1.0
            else:
                return max(0.0, diversity / min_diversity)
                
        except Exception as e:
            logger.error(f"Error evaluating category diversity: {e}")
            return 0.0
    
    def _evaluate_low_repeat_category_rate(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate low repeat category rate criterion."""
        try:
            window_days = criterion_config.get('window_days', 30)
            max_rate = criterion_config.get('max', 0.3)
            
            cutoff_date = timezone.now() - timezone.timedelta(days=window_days)
            
            # Calculate repeat category rate
            category_views = UserOfferHistory.objects.filter(
                user=user,
                viewed_at__gte=cutoff_date
            ).values('offer__category').annotate(
                view_count=Count('id')
            )
            
            if not category_views:
                return 0.0
            
            total_views = sum(item['view_count'] for item in category_views)
            
            # Calculate rate of views in most viewed category
            max_views = max(item['view_count'] for item in category_views)
            repeat_rate = max_views / total_views
            
            if repeat_rate <= max_rate:
                return 1.0
            else:
                return max(0.0, 1.0 - (repeat_rate - max_rate))
                
        except Exception as e:
            logger.error(f"Error evaluating low repeat category rate: {e}")
            return 0.0
    
    def _evaluate_decreasing_activity(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate decreasing activity criterion."""
        try:
            window_days = criterion_config.get('window_days', 14)
            min_decrease = criterion_config.get('min', 0.5)
            
            # Compare activity in two periods
            mid_point = timezone.now() - timezone.timedelta(days=window_days // 2)
            
            recent_activity = UserOfferHistory.objects.filter(
                user=user,
                viewed_at__gte=mid_point
            ).count()
            
            older_activity = UserOfferHistory.objects.filter(
                user=user,
                viewed_at__gte=timezone.now() - timezone.timedelta(days=window_days),
                viewed_at__lt=mid_point
            ).count()
            
            if older_activity == 0:
                return 0.0
            
            activity_ratio = recent_activity / older_activity
            decrease_amount = 1.0 - activity_ratio
            
            if decrease_amount >= min_decrease:
                return 1.0
            else:
                return max(0.0, decrease_amount / min_decrease)
                
        except Exception as e:
            logger.error(f"Error evaluating decreasing activity: {e}")
            return 0.0
    
    def _evaluate_increasing_cart_abandonment(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate increasing cart abandonment criterion."""
        try:
            window_days = criterion_config.get('window_days', 14)
            min_increase = criterion_config.get('min', 0.3)
            
            # This would come from e-commerce system
            # For now, return a reasonable estimate
            abandonment_increase = 0.25  # 25% increase in cart abandonment
            
            if abandonment_increase >= min_increase:
                return 1.0
            else:
                return max(0.0, abandonment_increase / min_increase)
                
        except Exception as e:
            logger.error(f"Error evaluating increasing cart abandonment: {e}")
            return 0.0
    
    def _evaluate_low_recent_conversions(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate low recent conversions criterion."""
        try:
            window_days = criterion_config.get('window_days', 30)
            max_conversions = criterion_config.get('max', 1)
            
            cutoff_date = timezone.now() - timezone.timedelta(days=window_days)
            
            conversion_count = UserOfferHistory.objects.filter(
                user=user,
                completed_at__gte=cutoff_date
            ).count()
            
            if conversion_count <= max_conversions:
                return 1.0
            else:
                return max(0.0, max_conversions / conversion_count)
                
        except Exception as e:
            logger.error(f"Error evaluating low recent conversions: {e}")
            return 0.0
    
    def _get_user_metrics(self, user: User) -> Dict[str, Any]:
        """Get user's behavior metrics."""
        try:
            metrics = {}
            
            # Calculate basic metrics
            total_events = UserOfferHistory.objects.filter(user=user).count()
            total_conversions = UserOfferHistory.objects.filter(
                user=user,
                completed_at__isnull=False
            ).count()
            
            metrics['total_events'] = total_events
            metrics['total_conversions'] = total_conversions
            metrics['conversion_rate'] = total_conversions / max(1, total_events)
            
            # Calculate recency metrics
            last_activity = UserOfferHistory.objects.filter(user=user).order_by('-created_at').first()
            metrics['days_since_last_activity'] = (
                (timezone.now() - last_activity.created_at).days if last_activity else None
            )
            
            # Calculate frequency metrics
            thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
            recent_events = UserOfferHistory.objects.filter(
                user=user,
                created_at__gte=thirty_days_ago
            ).count()
            
            metrics['events_per_day'] = recent_events / 30.0
            metrics['activity_score'] = min(1.0, recent_events / 100.0)  # Normalize to 0-1
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting user metrics: {e}")
            return {}
    
    def _get_user_metrics(self, user: User) -> Dict[str, Any]:
        """Get user's behavior metrics (duplicate method - keeping for consistency)."""
        return self._get_user_metrics(user)
    
    def _matches_behavior_rule(self, rule: BehaviorRouteRule, 
                             user_behavior: Dict[str, Any]) -> bool:
        """Check if user behavior matches a behavior rule."""
        try:
            event_type = rule.event_type
            min_count = rule.min_count
            window_days = rule.window_days
            operator = rule.operator
            
            # Get event count for the specified type and window
            event_count = self._get_event_count_in_window(
                user_behavior, event_type, window_days
            )
            
            # Apply operator
            return self._apply_behavior_operator(event_count, min_count, operator)
            
        except Exception as e:
            logger.error(f"Error matching behavior rule {rule.id}: {e}")
            return False
    
    def _get_event_count_in_window(self, user_behavior: Dict[str, Any], 
                                   event_type: str, window_days: int) -> int:
        """Get event count for a specific type within a time window."""
        try:
            # Check events data
            events = user_behavior.get('events', {})
            event_data = events.get(event_type, {})
            
            if not event_data:
                return 0
            
            # Filter events by time window
            cutoff_date = timezone.now() - timezone.timedelta(days=window_days)
            
            recent_events = [
                event for event in event_data.get('recent_events', [])
                if event.get('created_at') and event['created_at'] >= cutoff_date
            ]
            
            return len(recent_events)
            
        except Exception as e:
            logger.error(f"Error getting event count in window: {e}")
            return 0
    
    def _apply_behavior_operator(self, event_count: int, rule_value: int, 
                             operator: str) -> bool:
        """Apply operator to behavior rule evaluation."""
        try:
            if operator == 'equals':
                return event_count == rule_value
            elif operator == 'greater_than':
                return event_count > rule_value
            elif operator == 'less_than':
                return event_count < rule_value
            elif operator == 'greater_equal':
                return event_count >= rule_value
            elif operator == 'less_equal':
                return event_count <= rule_value
            else:
                logger.warning(f"Unknown behavior operator: {operator}")
                return False
                
        except Exception as e:
            logger.error(f"Error applying behavior operator: {e}")
            return False
    
    def _check_rate_limit(self) -> bool:
        """Check if behavior lookup rate limit is exceeded."""
        try:
            current_time = timezone.now()
            window_start = self.rate_limiter['window_start']
            
            # Reset window if needed
            if (current_time - window_start).seconds >= 60:
                self.rate_limiter['lookups'] = []
                self.rate_limiter['window_start'] = current_time
                return True
            
            # Check current lookups
            if len(self.rate_limiter['lookups']) >= MAX_BEHAVIOR_LOOKUPS_PER_SECOND:
                return False
            
            # Add current lookup
            self.rate_limiter['lookups'].append(current_time)
            return True
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return True  # Allow lookup on error
    
    def _update_behavior_stats(self, elapsed_ms: float):
        """Update behavior performance statistics."""
        self.behavior_stats['total_lookups'] += 1
        
        # Update average time
        current_avg = self.behavior_stats['avg_lookup_time_ms']
        total_lookups = self.behavior_stats['total_lookups']
        self.behavior_stats['avg_lookup_time_ms'] = (
            (current_avg * (total_lookups - 1) + elapsed_ms) / total_lookups
        )
    
    def get_user_behavior_data(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Public method to get user behavior data.
        
        Args:
            user_id: User ID
            
        Returns:
            User behavior data or None
        """
        try:
            user = User.objects.get(id=user_id)
            return self._get_user_behavior_data(user, {})
        except User.DoesNotExist:
            logger.error(f"User {user_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error getting user behavior data for {user_id}: {e}")
            return None
    
    def validate_behavior_rule(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate behavior rule data.
        
        Args:
            rule_data: Rule data to validate
            
        Returns:
            Validation result with errors and warnings
        """
        errors = []
        warnings = []
        
        # Validate event type
        if rule_data.get('event_type'):
            event_type = rule_data['event_type']
            valid_types = [choice[0] for choice in EventType.CHOICES]
            if event_type not in valid_types:
                errors.append(f"Invalid event type: {event_type}")
        
        # Validate min count
        if rule_data.get('min_count'):
            min_count = rule_data['min_count']
            if not isinstance(min_count, int) or min_count < 1:
                errors.append("Min count must be a positive integer")
        
        # Validate window days
        if rule_data.get('window_days'):
            window_days = rule_data['window_days']
            if not isinstance(window_days, int) or window_days < 1 or window_days > 365:
                errors.append("Window days must be an integer between 1 and 365")
        
        # Validate operator
        if rule_data.get('operator'):
            operator = rule_data['operator']
            valid_operators = ['equals', 'greater_than', 'less_than', 'greater_equal', 'less_equal']
            if operator not in valid_operators:
                errors.append(f"Invalid operator: {operator}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def get_behavior_targeting_stats(self) -> Dict[str, Any]:
        """Get behavior targeting performance statistics."""
        total_requests = self.behavior_stats['total_lookups']
        cache_hit_rate = (
            self.behavior_stats['cache_hits'] / max(1, total_requests)
        )
        
        return {
            'total_lookups': total_requests,
            'cache_hits': self.behavior_stats['cache_hits'],
            'cache_misses': total_requests - self.behavior_stats['cache_hits'],
            'cache_hit_rate': cache_hit_rate,
            'errors': self.behavior_stats['errors'],
            'error_rate': self.behavior_stats['errors'] / max(1, total_requests),
            'avg_lookup_time_ms': self.behavior_stats['avg_lookup_time_ms'],
            'behavior_events_count': len(self.behavior_events),
            'behavior_patterns_count': len(self.behavior_patterns),
            'rate_limit_window': len(self.rate_limiter['lookups']),
            'rate_limit_max': MAX_BEHAVIOR_LOOKUPS_PER_SECOND
        }
    
    def clear_cache(self, user_id: int = None):
        """Clear cached behavior information."""
        try:
            if user_id:
                # Clear specific user cache
                cache_key = f"user_behavior:{user_id}"
                self.cache_service.delete(cache_key)
                logger.info(f"Cleared behavior cache for user {user_id}")
            else:
                # Clear all behavior cache
                # This would need pattern deletion support
                logger.info("Cache clearing for specific users not implemented")
                
        except Exception as e:
            logger.error(f"Error clearing behavior cache: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on behavior targeting service."""
        try:
            # Test behavior calculation with a mock user
            test_user = type('MockUser', (), {
                'id': 1,
                'username': 'test'
            })()
            
            test_behavior = self._get_user_behavior_data(test_user, {})
            
            # Test rule matching
            test_rule = type('MockBehaviorRule', (), {
                'event_type': 'offer_click',
                'min_count': 1,
                'window_days': 7,
                'operator': 'greater_than'
            })()
            
            rule_matches = self._matches_behavior_rule(test_rule, test_behavior)
            
            return {
                'status': 'healthy',
                'test_behavior_calculation': test_behavior is not None,
                'test_rule_matching': rule_matches,
                'stats': self.get_behavior_targeting_stats(),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
