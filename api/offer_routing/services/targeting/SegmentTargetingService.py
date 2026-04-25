"""
User Segment Targeting Service

Handles user segment evaluation for tier/new/active/churned
user segment targeting rules in offer routing system.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum
from django.core.cache import cache
from ....models import (
    OfferRoute, UserSegmentRule, RoutingDecisionLog,
    UserOfferHistory, UserPreferenceVector
)
from ....choices import UserSegmentType
from ....constants import (
    SEGMENT_CACHE_TIMEOUT, USER_SEGMENT_UPDATE_INTERVAL,
    MIN_SEGMENT_SAMPLE_SIZE, SEGMENT_CONFIDENCE_THRESHOLD
)
from ....exceptions import TargetingError, SegmentationError
from ....utils import get_user_segment_info, calculate_user_activity_score

User = get_user_model()
logger = logging.getLogger(__name__)


class SegmentTargetingService:
    """
    Service for user segment targeting rules.
    
    Provides user segmentation and matching against
    segment-based targeting rules for offer routing.
    
    Performance targets:
    - Segment evaluation: <5ms per user
    - Rule matching: <2ms per rule
    - Cache hit rate: >95%
    """
    
    def __init__(self):
        self.cache_service = cache
        self.segmentation_stats = {
            'total_evaluations': 0,
            'cache_hits': 0,
            'errors': 0,
            'avg_evaluation_time_ms': 0.0
        }
        self.segment_definitions = self._initialize_segment_definitions()
    
    def _initialize_segment_definitions(self) -> Dict[str, Any]:
        """Initialize user segment definitions and criteria."""
        return {
            'new': {
                'name': 'New User',
                'description': 'Recently registered users',
                'criteria': {
                    'days_since_registration': {'max': 30},
                    'total_interactions': {'max': 10},
                    'conversion_events': {'max': 2}
                },
                'weight': 1.0,
                'priority': 1
            },
            'active': {
                'name': 'Active User',
                'description': 'Regularly engaged users',
                'criteria': {
                    'days_since_last_activity': {'max': 7},
                    'total_interactions': {'min': 20},
                    'monthly_sessions': {'min': 5}
                },
                'weight': 2.0,
                'priority': 2
            },
            'premium': {
                'name': 'Premium User',
                'description': 'High-value paying users',
                'criteria': {
                    'is_premium': True,
                    'total_revenue': {'min': 100.0},
                    'subscription_tier': {'in': ['gold', 'platinum', 'diamond']}
                },
                'weight': 3.0,
                'priority': 3
            },
            'churned': {
                'name': 'Churned User',
                'description': 'Inactive or at-risk users',
                'criteria': {
                    'days_since_last_activity': {'min': 30},
                    'days_since_registration': {'min': 60},
                    'recent_conversions': {'max': 1}
                },
                'weight': 0.5,
                'priority': 4
            },
            'high_value': {
                'name': 'High Value User',
                'description': 'Users with high lifetime value',
                'criteria': {
                    'lifetime_revenue': {'min': 500.0},
                    'avg_order_value': {'min': 50.0},
                    'conversion_rate': {'min': 0.05}
                },
                'weight': 2.5,
                'priority': 5
            },
            'low_engagement': {
                'name': 'Low Engagement User',
                'description': 'Users with low activity levels',
                'criteria': {
                    'days_since_last_activity': {'min': 14, 'max': 60},
                    'session_frequency': {'max': 2},  # per month
                    'page_views_per_session': {'max': 3}
                },
                'weight': 0.8,
                'priority': 6
            }
        }
    
    def matches_route(self, route: OfferRoute, user: User, 
                     user_segment: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Check if route matches user's segment.
        
        Args:
            route: Route to check
            user: User object
            user_segment: User segment information
            context: User context
            
        Returns:
            True if route matches segment-wise, False otherwise
        """
        try:
            # Get segment rules for route
            segment_rules = route.segment_rules.filter(is_active=True).order_by('priority')
            
            if not segment_rules:
                return True  # No segment restrictions
            
            # Get user's segment information
            user_segments = self._get_user_segments(user, context)
            
            if not user_segments:
                logger.warning(f"Could not determine segments for user {user.id}")
                return False  # Cannot apply segment targeting without segments
            
            # Check each segment rule
            for rule in segment_rules:
                if self._matches_segment_rule(rule, user_segments):
                    return True  # Segment rule matches
            
            # If no rules matched, return False
            return False
            
        except Exception as e:
            logger.error(f"Error checking segment targeting for route {route.id}: {e}")
            return False
    
    def _get_user_segments(self, user: User, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get user's segment information with caching."""
        try:
            # Check cache first
            cache_key = f"user_segments:{user.id}"
            cached_segments = self.cache_service.get(cache_key)
            
            if cached_segments:
                self.segmentation_stats['cache_hits'] += 1
                return cached_segments
            
            start_time = timezone.now()
            
            # Calculate user segments
            user_segments = []
            
            for segment_name, segment_def in self.segment_definitions.items():
                segment_result = self._evaluate_user_segment(user, segment_name, segment_def)
                
                if segment_result['matches']:
                    user_segments.append({
                        'segment_type': segment_name,
                        'segment_name': segment_def['name'],
                        'segment_description': segment_def['description'],
                        'weight': segment_def['weight'],
                        'priority': segment_def['priority'],
                        'confidence': segment_result['confidence'],
                        'criteria_scores': segment_result['criteria_scores'],
                        'calculated_at': timezone.now().isoformat()
                    })
            
            # Sort by priority (lower priority number = higher priority)
            user_segments.sort(key=lambda x: x['priority'])
            
            # Cache result
            self.cache_service.set(cache_key, user_segments, SEGMENT_CACHE_TIMEOUT)
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_segmentation_stats(elapsed_ms)
            
            return user_segments
            
        except Exception as e:
            logger.error(f"Error getting user segments for {user.id}: {e}")
            self.segmentation_stats['errors'] += 1
            return []
    
    def _evaluate_user_segment(self, user: User, segment_name: str, 
                               segment_def: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate if user matches a specific segment."""
        try:
            criteria = segment_def['criteria']
            criteria_scores = {}
            total_score = 0.0
            criteria_count = len(criteria)
            
            # Evaluate each criterion
            for criterion_name, criterion_config in criteria.items():
                score = self._evaluate_criterion(user, criterion_name, criterion_config)
                criteria_scores[criterion_name] = score
                total_score += score
            
            # Calculate average score as confidence
            confidence = total_score / criteria_count if criteria_count > 0 else 0.0
            
            # Determine if user matches segment
            matches = confidence >= SEGMENT_CONFIDENCE_THRESHOLD
            
            return {
                'matches': matches,
                'confidence': confidence,
                'criteria_scores': criteria_scores,
                'total_score': total_score
            }
            
        except Exception as e:
            logger.error(f"Error evaluating segment {segment_name}: {e}")
            return {
                'matches': False,
                'confidence': 0.0,
                'criteria_scores': {},
                'total_score': 0.0
            }
    
    def _evaluate_criterion(self, user: User, criterion_name: str, 
                           criterion_config: Dict[str, Any]) -> float:
        """Evaluate a single segment criterion."""
        try:
            if criterion_name == 'days_since_registration':
                return self._evaluate_days_since_registration(user, criterion_config)
            elif criterion_name == 'days_since_last_activity':
                return self._evaluate_days_since_last_activity(user, criterion_config)
            elif criterion_name == 'total_interactions':
                return self._evaluate_total_interactions(user, criterion_config)
            elif criterion_name == 'conversion_events':
                return self._evaluate_conversion_events(user, criterion_config)
            elif criterion_name == 'is_premium':
                return self._evaluate_is_premium(user, criterion_config)
            elif criterion_name == 'total_revenue':
                return self._evaluate_total_revenue(user, criterion_config)
            elif criterion_name == 'subscription_tier':
                return self._evaluate_subscription_tier(user, criterion_config)
            elif criterion_name == 'lifetime_revenue':
                return self._evaluate_lifetime_revenue(user, criterion_config)
            elif criterion_name == 'avg_order_value':
                return self._evaluate_avg_order_value(user, criterion_config)
            elif criterion_name == 'conversion_rate':
                return self._evaluate_conversion_rate(user, criterion_config)
            elif criterion_name == 'monthly_sessions':
                return self._evaluate_monthly_sessions(user, criterion_config)
            elif criterion_name == 'session_frequency':
                return self._evaluate_session_frequency(user, criterion_config)
            elif criterion_name == 'page_views_per_session':
                return self._evaluate_page_views_per_session(user, criterion_config)
            elif criterion_name == 'recent_conversions':
                return self._evaluate_recent_conversions(user, criterion_config)
            else:
                logger.warning(f"Unknown criterion: {criterion_name}")
                return 0.0
                
        except Exception as e:
            logger.error(f"Error evaluating criterion {criterion_name}: {e}")
            return 0.0
    
    def _evaluate_days_since_registration(self, user: User, 
                                       criterion_config: Dict[str, Any]) -> float:
        """Evaluate days since user registration."""
        try:
            days_since_reg = (timezone.now() - user.date_joined).days
            
            min_days = criterion_config.get('min', 0)
            max_days = criterion_config.get('max', float('inf'))
            
            if min_days <= days_since_reg <= max_days:
                return 1.0
            else:
                # Calculate partial score based on distance from range
                if days_since_reg < min_days:
                    return max(0.0, 1.0 - (min_days - days_since_reg) / min_days)
                else:
                    return max(0.0, 1.0 - (days_since_reg - max_days) / max_days)
                    
        except Exception as e:
            logger.error(f"Error evaluating days since registration: {e}")
            return 0.0
    
    def _evaluate_days_since_last_activity(self, user: User, 
                                        criterion_config: Dict[str, Any]) -> float:
        """Evaluate days since user's last activity."""
        try:
            last_activity = self._get_user_last_activity(user)
            
            if not last_activity:
                return 0.0  # No activity data
            
            days_since_activity = (timezone.now() - last_activity).days
            
            min_days = criterion_config.get('min', 0)
            max_days = criterion_config.get('max', float('inf'))
            
            if min_days <= days_since_activity <= max_days:
                return 1.0
            else:
                # Calculate partial score
                if days_since_activity < min_days:
                    return max(0.0, 1.0 - (min_days - days_since_activity) / min_days)
                else:
                    return max(0.0, 1.0 - (days_since_activity - max_days) / max_days)
                    
        except Exception as e:
            logger.error(f"Error evaluating days since last activity: {e}")
            return 0.0
    
    def _evaluate_total_interactions(self, user: User, 
                                   criterion_config: Dict[str, Any]) -> float:
        """Evaluate user's total interactions."""
        try:
            total_interactions = self._get_user_total_interactions(user)
            
            min_interactions = criterion_config.get('min', 0)
            max_interactions = criterion_config.get('max', float('inf'))
            
            if min_interactions <= total_interactions <= max_interactions:
                return 1.0
            else:
                # Calculate partial score
                if total_interactions < min_interactions:
                    return total_interactions / min_interactions
                else:
                    return max(0.0, 1.0 - (total_interactions - max_interactions) / max_interactions)
                    
        except Exception as e:
            logger.error(f"Error evaluating total interactions: {e}")
            return 0.0
    
    def _evaluate_conversion_events(self, user: User, 
                                  criterion_config: Dict[str, Any]) -> float:
        """Evaluate user's conversion events."""
        try:
            conversion_events = self._get_user_conversion_events(user)
            
            min_conversions = criterion_config.get('min', 0)
            max_conversions = criterion_config.get('max', float('inf'))
            
            if min_conversions <= conversion_events <= max_conversions:
                return 1.0
            else:
                # Calculate partial score
                if conversion_events < min_conversions:
                    return conversion_events / min_conversions if min_conversions > 0 else 0.0
                else:
                    return max(0.0, 1.0 - (conversion_events - max_conversions) / max_conversions)
                    
        except Exception as e:
            logger.error(f"Error evaluating conversion events: {e}")
            return 0.0
    
    def _evaluate_is_premium(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate if user is premium."""
        try:
            is_premium = getattr(user, 'is_premium', False)
            expected_value = criterion_config.get('value', True)
            
            return 1.0 if is_premium == expected_value else 0.0
            
        except Exception as e:
            logger.error(f"Error evaluating is premium: {e}")
            return 0.0
    
    def _evaluate_total_revenue(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate user's total revenue."""
        try:
            total_revenue = self._get_user_total_revenue(user)
            
            min_revenue = criterion_config.get('min', 0.0)
            max_revenue = criterion_config.get('max', float('inf'))
            
            if min_revenue <= total_revenue <= max_revenue:
                return 1.0
            else:
                # Calculate partial score
                if total_revenue < min_revenue:
                    return total_revenue / min_revenue if min_revenue > 0 else 0.0
                else:
                    return max(0.0, 1.0 - (total_revenue - min_revenue) / max_revenue)
                    
        except Exception as e:
            logger.error(f"Error evaluating total revenue: {e}")
            return 0.0
    
    def _evaluate_subscription_tier(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate user's subscription tier."""
        try:
            subscription_tier = getattr(user, 'subscription_tier', 'basic')
            valid_tiers = criterion_config.get('in', [])
            
            return 1.0 if subscription_tier in valid_tiers else 0.0
            
        except Exception as e:
            logger.error(f"Error evaluating subscription tier: {e}")
            return 0.0
    
    def _evaluate_lifetime_revenue(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate user's lifetime revenue."""
        try:
            lifetime_revenue = self._get_user_lifetime_revenue(user)
            
            min_revenue = criterion_config.get('min', 0.0)
            max_revenue = criterion_config.get('max', float('inf'))
            
            if min_revenue <= lifetime_revenue <= max_revenue:
                return 1.0
            else:
                # Calculate partial score
                if lifetime_revenue < min_revenue:
                    return lifetime_revenue / min_revenue if min_revenue > 0 else 0.0
                else:
                    return max(0.0, 1.0 - (lifetime_revenue - min_revenue) / max_revenue)
                    
        except Exception as e:
            logger.error(f"Error evaluating lifetime revenue: {e}")
            return 0.0
    
    def _evaluate_avg_order_value(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate user's average order value."""
        try:
            avg_order_value = self._get_user_avg_order_value(user)
            
            min_value = criterion_config.get('min', 0.0)
            max_value = criterion_config.get('max', float('inf'))
            
            if min_value <= avg_order_value <= max_value:
                return 1.0
            else:
                # Calculate partial score
                if avg_order_value < min_value:
                    return avg_order_value / min_value if min_value > 0 else 0.0
                else:
                    return max(0.0, 1.0 - (avg_order_value - min_value) / max_value)
                    
        except Exception as e:
            logger.error(f"Error evaluating average order value: {e}")
            return 0.0
    
    def _evaluate_conversion_rate(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate user's conversion rate."""
        try:
            conversion_rate = self._get_user_conversion_rate(user)
            
            min_rate = criterion_config.get('min', 0.0)
            max_rate = criterion_config.get('max', 1.0)
            
            if min_rate <= conversion_rate <= max_rate:
                return 1.0
            else:
                # Calculate partial score
                if conversion_rate < min_rate:
                    return conversion_rate / min_rate if min_rate > 0 else 0.0
                else:
                    return max(0.0, 1.0 - (conversion_rate - min_rate) / (1.0 - min_rate))
                    
        except Exception as e:
            logger.error(f"Error evaluating conversion rate: {e}")
            return 0.0
    
    def _evaluate_monthly_sessions(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate user's monthly session count."""
        try:
            monthly_sessions = self._get_user_monthly_sessions(user)
            
            min_sessions = criterion_config.get('min', 0)
            max_sessions = criterion_config.get('max', float('inf'))
            
            if min_sessions <= monthly_sessions <= max_sessions:
                return 1.0
            else:
                # Calculate partial score
                if monthly_sessions < min_sessions:
                    return monthly_sessions / min_sessions if min_sessions > 0 else 0.0
                else:
                    return max(0.0, 1.0 - (monthly_sessions - min_sessions) / max_sessions)
                    
        except Exception as e:
            logger.error(f"Error evaluating monthly sessions: {e}")
            return 0.0
    
    def _evaluate_session_frequency(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate user's session frequency."""
        try:
            session_frequency = self._get_user_session_frequency(user)
            
            min_frequency = criterion_config.get('min', 0)
            max_frequency = criterion_config.get('max', float('inf'))
            
            if min_frequency <= session_frequency <= max_frequency:
                return 1.0
            else:
                # Calculate partial score
                if session_frequency < min_frequency:
                    return session_frequency / min_frequency if min_frequency > 0 else 0.0
                else:
                    return max(0.0, 1.0 - (session_frequency - min_frequency) / max_frequency)
                    
        except Exception as e:
            logger.error(f"Error evaluating session frequency: {e}")
            return 0.0
    
    def _evaluate_page_views_per_session(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate user's page views per session."""
        try:
            page_views_per_session = self._get_user_page_views_per_session(user)
            
            min_views = criterion_config.get('min', 0)
            max_views = criterion_config.get('max', float('inf'))
            
            if min_views <= page_views_per_session <= max_views:
                return 1.0
            else:
                # Calculate partial score
                if page_views_per_session < min_views:
                    return page_views_per_session / min_views if min_views > 0 else 0.0
                else:
                    return max(0.0, 1.0 - (page_views_per_session - min_views) / max_views)
                    
        except Exception as e:
            logger.error(f"Error evaluating page views per session: {e}")
            return 0.0
    
    def _evaluate_recent_conversions(self, user: User, criterion_config: Dict[str, Any]) -> float:
        """Evaluate user's recent conversions."""
        try:
            recent_conversions = self._get_user_recent_conversions(user)
            
            min_conversions = criterion_config.get('min', 0)
            max_conversions = criterion_config.get('max', float('inf'))
            
            if min_conversions <= recent_conversions <= max_conversions:
                return 1.0
            else:
                # Calculate partial score
                if recent_conversions < min_conversions:
                    return recent_conversions / min_conversions if min_conversions > 0 else 0.0
                else:
                    return max(0.0, 1.0 - (recent_conversions - min_conversions) / max_conversions)
                    
        except Exception as e:
            logger.error(f"Error evaluating recent conversions: {e}")
            return 0.0
    
    def _get_user_last_activity(self, user: User) -> Optional[timezone.datetime]:
        """Get user's last activity timestamp."""
        try:
            # Check various activity sources
            activity_sources = [
                UserOfferHistory.objects.filter(user=user).order_by('-created_at').first(),
                RoutingDecisionLog.objects.filter(user=user).order_by('-created_at').first()
            ]
            
            latest_activity = None
            
            for activity in activity_sources:
                if activity and activity.created_at:
                    if not latest_activity or activity.created_at > latest_activity:
                        latest_activity = activity.created_at
            
            # Check user's last_login field
            last_login = getattr(user, 'last_login', None)
            if last_login and (not latest_activity or last_login > latest_activity):
                latest_activity = last_login
            
            return latest_activity
            
        except Exception as e:
            logger.error(f"Error getting user last activity: {e}")
            return None
    
    def _get_user_total_interactions(self, user: User) -> int:
        """Get user's total interaction count."""
        try:
            return UserOfferHistory.objects.filter(user=user).count()
        except Exception as e:
            logger.error(f"Error getting user total interactions: {e}")
            return 0
    
    def _get_user_conversion_events(self, user: User) -> int:
        """Get user's total conversion events."""
        try:
            return UserOfferHistory.objects.filter(
                user=user,
                completed_at__isnull=False
            ).count()
        except Exception as e:
            logger.error(f"Error getting user conversion events: {e}")
            return 0
    
    def _get_user_total_revenue(self, user: User) -> float:
        """Get user's total revenue."""
        try:
            revenue_data = UserOfferHistory.objects.filter(
                user=user,
                completed_at__isnull=False
            ).aggregate(
                total_revenue=Sum('conversion_value')
            )
            
            return float(revenue_data['total_revenue'] or 0.0)
            
        except Exception as e:
            logger.error(f"Error getting user total revenue: {e}")
            return 0.0
    
    def _get_user_lifetime_revenue(self, user: User) -> float:
        """Get user's lifetime revenue (same as total revenue for now)."""
        return self._get_user_total_revenue(user)
    
    def _get_user_avg_order_value(self, user: User) -> float:
        """Get user's average order value."""
        try:
            avg_data = UserOfferHistory.objects.filter(
                user=user,
                completed_at__isnull=False
            ).aggregate(
                avg_value=Avg('conversion_value')
            )
            
            return float(avg_data['avg_value'] or 0.0)
            
        except Exception as e:
            logger.error(f"Error getting user average order value: {e}")
            return 0.0
    
    def _get_user_conversion_rate(self, user: User) -> float:
        """Get user's conversion rate."""
        try:
            total_views = UserOfferHistory.objects.filter(user=user).count()
            total_conversions = UserOfferHistory.objects.filter(
                user=user,
                completed_at__isnull=False
            ).count()
            
            if total_views == 0:
                return 0.0
            
            return total_conversions / total_views
            
        except Exception as e:
            logger.error(f"Error getting user conversion rate: {e}")
            return 0.0
    
    def _get_user_monthly_sessions(self, user: User) -> int:
        """Get user's monthly session count."""
        try:
            # This would typically come from an analytics system
            # For now, estimate from offer history
            month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            return UserOfferHistory.objects.filter(
                user=user,
                created_at__gte=month_start
            ).distinct('created_at__date').count()
            
        except Exception as e:
            logger.error(f"Error getting user monthly sessions: {e}")
            return 0
    
    def _get_user_session_frequency(self, user: User) -> float:
        """Get user's session frequency (sessions per day)."""
        try:
            monthly_sessions = self._get_user_monthly_sessions(user)
            days_in_month = (timezone.now().replace(day=1) + timezone.timedelta(days=32)).replace(day=1) - timezone.now().replace(day=1)
            
            if days_in_month.days == 0:
                return 0.0
            
            return monthly_sessions / days_in_month.days
            
        except Exception as e:
            logger.error(f"Error getting user session frequency: {e}")
            return 0.0
    
    def _get_user_page_views_per_session(self, user: User) -> float:
        """Get user's average page views per session."""
        try:
            # This would typically come from an analytics system
            # For now, return a reasonable default
            return 3.5  # Average page views per session
            
        except Exception as e:
            logger.error(f"Error getting user page views per session: {e}")
            return 0.0
    
    def _get_user_recent_conversions(self, user: User) -> int:
        """Get user's recent conversions (last 30 days)."""
        try:
            recent_cutoff = timezone.now() - timezone.timedelta(days=30)
            
            return UserOfferHistory.objects.filter(
                user=user,
                completed_at__isnull=False,
                completed_at__gte=recent_cutoff
            ).count()
            
        except Exception as e:
            logger.error(f"Error getting user recent conversions: {e}")
            return 0
    
    def _matches_segment_rule(self, rule: UserSegmentRule, 
                             user_segments: List[Dict[str, Any]]) -> bool:
        """Check if user segments match a segment rule."""
        try:
            user_segment_types = [seg['segment_type'] for seg in user_segments]
            
            # Check if user has the required segment type
            if rule.segment_type in user_segment_types:
                # Get the specific segment data
                user_segment = next(
                    (seg for seg in user_segments if seg['segment_type'] == rule.segment_type),
                    None
                )
                
                if user_segment:
                    return self._evaluate_segment_operator(
                        user_segment['confidence'],
                        rule.value,
                        rule.operator
                    )
            
            return False
            
        except Exception as e:
            logger.error(f"Error matching segment rule {rule.id}: {e}")
            return False
    
    def _evaluate_segment_operator(self, user_value: float, rule_value: str, 
                                operator: str) -> bool:
        """Evaluate segment operator."""
        try:
            # Convert rule value to appropriate type
            if operator in ['equals', 'not_equals']:
                return self._evaluate_equality_operator(user_value, rule_value, operator)
            elif operator in ['in', 'not_in']:
                return self._evaluate_in_operator(user_value, rule_value, operator)
            elif operator in ['contains', 'not_contains']:
                return self._evaluate_contains_operator(user_value, rule_value, operator)
            elif operator in ['greater_than', 'less_than', 'greater_equal', 'less_equal']:
                return self._evaluate_comparison_operator(user_value, rule_value, operator)
            else:
                logger.warning(f"Unknown segment operator: {operator}")
                return False
                
        except Exception as e:
            logger.error(f"Error evaluating segment operator: {e}")
            return False
    
    def _evaluate_equality_operator(self, user_value: float, rule_value: str, 
                                  operator: str) -> bool:
        """Evaluate equality operators."""
        try:
            # Convert rule value to number if possible
            try:
                numeric_value = float(rule_value)
                if operator == 'equals':
                    return abs(user_value - numeric_value) < 0.01
                else:  # not_equals
                    return abs(user_value - numeric_value) >= 0.01
            except ValueError:
                # Treat as string comparison
                str_value = str(user_value)
                if operator == 'equals':
                    return str_value == rule_value
                else:  # not_equals
                    return str_value != rule_value
                    
        except Exception as e:
            logger.error(f"Error evaluating equality operator: {e}")
            return False
    
    def _evaluate_in_operator(self, user_value: float, rule_value: str, 
                             operator: str) -> bool:
        """Evaluate in/not-in operators."""
        try:
            # Parse rule value as list
            try:
                import json
                value_list = json.loads(rule_value)
                if not isinstance(value_list, list):
                    value_list = [rule_value]
            except (json.JSONDecodeError, ValueError):
                value_list = [rule_value]
            
            # Check membership
            is_in = user_value in value_list
            
            if operator == 'in':
                return is_in
            else:  # not_in
                return not is_in
                
        except Exception as e:
            logger.error(f"Error evaluating in operator: {e}")
            return False
    
    def _evaluate_contains_operator(self, user_value: float, rule_value: str, 
                                  operator: str) -> bool:
        """Evaluate contains operators."""
        try:
            str_value = str(user_value)
            contains = rule_value in str_value
            
            if operator == 'contains':
                return contains
            else:  # not_contains
                return not contains
                
        except Exception as e:
            logger.error(f"Error evaluating contains operator: {e}")
            return False
    
    def _evaluate_comparison_operator(self, user_value: float, rule_value: str, 
                                    operator: str) -> bool:
        """Evaluate comparison operators."""
        try:
            numeric_value = float(rule_value)
            
            if operator == 'greater_than':
                return user_value > numeric_value
            elif operator == 'less_than':
                return user_value < numeric_value
            elif operator == 'greater_equal':
                return user_value >= numeric_value
            elif operator == 'less_equal':
                return user_value <= numeric_value
            else:
                return False
                
        except (ValueError, TypeError) as e:
            logger.error(f"Error evaluating comparison operator: {e}")
            return False
    
    def _update_segmentation_stats(self, elapsed_ms: float):
        """Update segmentation performance statistics."""
        self.segmentation_stats['total_evaluations'] += 1
        
        # Update average time
        current_avg = self.segmentation_stats['avg_evaluation_time_ms']
        total_evaluations = self.segmentation_stats['total_evaluations']
        self.segmentation_stats['avg_evaluation_time_ms'] = (
            (current_avg * (total_evaluations - 1) + elapsed_ms) / total_evaluations
        )
    
    def get_user_segments(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Public method to get user segments.
        
        Args:
            user_id: User ID
            
        Returns:
            List of user segments
        """
        try:
            user = User.objects.get(id=user_id)
            return self._get_user_segments(user, {})
        except User.DoesNotExist:
            logger.error(f"User {user_id} not found")
            return []
        except Exception as e:
            logger.error(f"Error getting user segments for {user_id}: {e}")
            return []
    
    def validate_segment_rule(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate segment rule data.
        
        Args:
            rule_data: Rule data to validate
            
        Returns:
            Validation result with errors and warnings
        """
        errors = []
        warnings = []
        
        # Validate segment type
        if rule_data.get('segment_type'):
            segment_type = rule_data['segment_type']
            valid_types = [choice[0] for choice in UserSegmentType.CHOICES]
            if segment_type not in valid_types:
                errors.append(f"Invalid segment type: {segment_type}")
        
        # Validate operator
        if rule_data.get('operator'):
            operator = rule_data['operator']
            valid_operators = ['equals', 'not_equals', 'in', 'not_in', 'contains', 'not_contains',
                              'greater_than', 'less_than', 'greater_equal', 'less_equal']
            if operator not in valid_operators:
                errors.append(f"Invalid operator: {operator}")
        
        # Validate value
        if rule_data.get('value'):
            value = rule_data['value']
            if not value or len(str(value).strip()) == 0:
                errors.append("Rule value cannot be empty")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def get_segmentation_stats(self) -> Dict[str, Any]:
        """Get segmentation performance statistics."""
        total_requests = self.segmentation_stats['total_evaluations']
        cache_hit_rate = (
            self.segmentation_stats['cache_hits'] / max(1, total_requests)
        )
        
        return {
            'total_evaluations': total_requests,
            'cache_hits': self.segmentation_stats['cache_hits'],
            'cache_misses': total_requests - self.segmentation_stats['cache_hits'],
            'cache_hit_rate': cache_hit_rate,
            'errors': self.segmentation_stats['errors'],
            'error_rate': self.segmentation_stats['errors'] / max(1, total_requests),
            'avg_evaluation_time_ms': self.segmentation_stats['avg_evaluation_time_ms'],
            'segment_definitions_count': len(self.segment_definitions)
        }
    
    def clear_cache(self, user_id: int = None):
        """Clear cached segment information."""
        try:
            if user_id:
                # Clear specific user cache
                cache_key = f"user_segments:{user_id}"
                self.cache_service.delete(cache_key)
                logger.info(f"Cleared segment cache for user {user_id}")
            else:
                # Clear all segment cache
                # This would need pattern deletion support
                logger.info("Cache clearing for specific users not implemented")
                
        except Exception as e:
            logger.error(f"Error clearing segment cache: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on segment targeting service."""
        try:
            # Test segment evaluation with a mock user
            test_user = type('MockUser', (), {
                'id': 1,
                'username': 'test',
                'date_joined': timezone.now() - timezone.timedelta(days=15),
                'is_premium': False,
                'last_login': timezone.now() - timezone.timedelta(days=2)
            })()
            
            test_segments = self._get_user_segments(test_user, {})
            
            # Test rule matching
            test_rule = type('MockSegmentRule', (), {
                'segment_type': 'new',
                'value': 'true',
                'operator': 'equals'
            })()
            
            rule_matches = self._matches_segment_rule(test_rule, test_segments)
            
            return {
                'status': 'healthy',
                'test_segment_evaluation': len(test_segments) > 0,
                'test_rule_matching': rule_matches,
                'stats': self.get_segmentation_stats(),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
