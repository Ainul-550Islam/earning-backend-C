"""
Utility functions for Offer Routing System
"""

import hashlib
import json
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from .constants import (
    CACHE_PREFIX, ROUTING_CACHE_TIMEOUT, SCORE_CACHE_TIMEOUT,
    MAX_ROUTING_TIME_MS, DEFAULT_AB_TEST_SPLIT_PERCENTAGE
)
from .enums import (
    CacheKeyPattern, LogLevel, AggregationType, ComparisonOperator,
    SortOrder, RoutingStrategy, PersonalizationLevel
)

logger = logging.getLogger(__name__)


def generate_cache_key(pattern: str, **kwargs) -> str:
    """Generate cache key with pattern and parameters."""
    try:
        return pattern.format(**kwargs)
    except KeyError as e:
        logger.error(f"Missing cache key parameter: {e}")
        raise ValueError(f"Missing cache key parameter: {e}")


def get_routing_cache_key(user_id: int, context_hash: str) -> str:
    """Generate routing cache key."""
    return generate_cache_key(
        CacheKeyPattern.ROUTING,
        user_id=user_id,
        context_hash=context_hash
    )


def get_score_cache_key(offer_id: int, user_id: int) -> str:
    """Generate score cache key."""
    return generate_cache_key(
        CacheKeyPattern.SCORE,
        offer_id=offer_id,
        user_id=user_id
    )


def get_cap_cache_key(offer_id: int, user_id: int) -> str:
    """Generate cap cache key."""
    return generate_cache_key(
        CacheKeyPattern.CAP,
        offer_id=offer_id,
        user_id=user_id
    )


def get_affinity_cache_key(user_id: int, category: str) -> str:
    """Generate affinity cache key."""
    return generate_cache_key(
        CacheKeyPattern.AFFINITY,
        user_id=user_id,
        category=category
    )


def hash_context(context: Dict[str, Any]) -> str:
    """Create hash from context data."""
    context_str = json.dumps(context, sort_keys=True)
    return hashlib.md5(context_str.encode()).hexdigest()


def calculate_score(
    epc: float = 0.0,
    cr: float = 0.0,
    relevance: float = 0.0,
    freshness: float = 0.0,
    weights: Optional[Dict[str, float]] = None
) -> float:
    """Calculate weighted score for an offer."""
    if weights is None:
        weights = {
            'epc': 0.4,
            'cr': 0.3,
            'relevance': 0.2,
            'freshness': 0.1
        }
    
    score = (
        (epc * weights.get('epc', 0.4)) +
        (cr * weights.get('cr', 0.3)) +
        (relevance * weights.get('relevance', 0.2)) +
        (freshness * weights.get('freshness', 0.1))
    )
    
    return min(score, 100.0)  # Cap at 100


def calculate_freshness_score(created_at: datetime, decay_days: int = 30) -> float:
    """Calculate freshness score based on creation date."""
    now = timezone.now()
    age_days = (now - created_at).days
    
    if age_days >= decay_days:
        return 0.0
    
    # Linear decay from 1.0 to 0.0
    freshness = 1.0 - (age_days / decay_days)
    return max(freshness, 0.0)


def calculate_cr_score(conversions: int, impressions: int) -> float:
    """Calculate conversion rate score."""
    if impressions == 0:
        return 0.0
    
    cr = conversions / impressions
    return min(cr * 100, 100.0)  # Convert to percentage and cap at 100


def normalize_score(score: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Normalize score to 0-100 range."""
    if score < min_val:
        return min_val
    if score > max_val:
        return max_val
    
    # Linear normalization
    return ((score - min_val) / (max_val - min_val)) * 100.0


def calculate_percentile_rank(scores: List[float], target_score: float) -> float:
    """Calculate percentile rank of target score."""
    if not scores:
        return 0.0
    
    scores_sorted = sorted(scores)
    rank = 0
    for score in scores_sorted:
        if score <= target_score:
            rank += 1
    
    percentile = (rank / len(scores)) * 100
    return percentile


def apply_diversity_rules(
    ranked_offers: List[Dict[str, Any]],
    max_per_category: int = 3,
    max_per_merchant: int = 2
) -> List[Dict[str, Any]]:
    """Apply diversity rules to ranked offers."""
    selected_offers = []
    category_counts = {}
    merchant_counts = {}
    
    for offer in ranked_offers:
        category = offer.get('category', 'default')
        merchant = offer.get('merchant', 'default')
        
        # Check category diversity
        if category_counts.get(category, 0) >= max_per_category:
            continue
        
        # Check merchant diversity
        if merchant_counts.get(merchant, 0) >= max_per_merchant:
            continue
        
        selected_offers.append(offer)
        category_counts[category] = category_counts.get(category, 0) + 1
        merchant_counts[merchant] = merchant_counts.get(merchant, 0) + 1
    
    return selected_offers


def calculate_statistical_significance(
    control_conversions: int,
    control_impressions: int,
    variant_conversions: int,
    variant_impressions: int,
    confidence_level: float = 0.95
) -> Dict[str, Any]:
    """Calculate statistical significance for A/B test."""
    # Calculate conversion rates
    control_cr = control_conversions / control_impressions if control_impressions > 0 else 0
    variant_cr = variant_conversions / variant_impressions if variant_impressions > 0 else 0
    
    # Calculate pooled proportion
    pooled_cr = (control_conversions + variant_conversions) / (control_impressions + variant_impressions)
    pooled_variance = pooled_cr * (1 - pooled_cr) / (control_impressions + variant_impressions)
    
    # Calculate Z-score
    diff = variant_cr - control_cr
    standard_error = math.sqrt(pooled_variance * (1/control_impressions + 1/variant_impressions))
    z_score = diff / standard_error if standard_error > 0 else 0
    
    # Calculate p-value (simplified)
    from scipy import stats
    p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))
    
    # Determine significance
    is_significant = p_value < (1 - confidence_level)
    
    return {
        'control_cr': control_cr,
        'variant_cr': variant_cr,
        'difference': diff,
        'z_score': z_score,
        'p_value': p_value,
        'is_significant': is_significant,
        'confidence_level': confidence_level
    }


def extract_device_info(user_agent: str) -> Dict[str, str]:
    """Extract device information from user agent string."""
    device_info = {
        'device_type': 'desktop',
        'os': 'unknown',
        'browser': 'unknown'
    }
    
    user_agent_lower = user_agent.lower()
    
    # Device type detection
    if any(mobile in user_agent_lower for mobile in ['mobile', 'android', 'iphone', 'ipad']):
        device_info['device_type'] = 'mobile'
    elif 'tablet' in user_agent_lower or 'ipad' in user_agent_lower:
        device_info['device_type'] = 'tablet'
    elif 'tv' in user_agent_lower:
        device_info['device_type'] = 'smart_tv'
    
    # OS detection
    if 'windows' in user_agent_lower:
        device_info['os'] = 'windows'
    elif 'mac' in user_agent_lower or 'os x' in user_agent_lower:
        device_info['os'] = 'macos'
    elif 'linux' in user_agent_lower:
        device_info['os'] = 'linux'
    elif 'android' in user_agent_lower:
        device_info['os'] = 'android'
    elif 'iphone' in user_agent_lower or 'ipad' in user_agent_lower:
        device_info['os'] = 'ios'
    
    # Browser detection
    if 'chrome' in user_agent_lower:
        device_info['browser'] = 'chrome'
    elif 'firefox' in user_agent_lower:
        device_info['browser'] = 'firefox'
    elif 'safari' in user_agent_lower:
        device_info['browser'] = 'safari'
    elif 'edge' in user_agent_lower or 'edg' in user_agent_lower:
        device_info['browser'] = 'edge'
    elif 'opera' in user_agent_lower:
        device_info['browser'] = 'opera'
    elif 'msie' in user_agent_lower or 'trident' in user_agent_lower:
        device_info['browser'] = 'ie'
    
    return device_info


def get_geo_location_from_ip(ip_address: str) -> Optional[Dict[str, str]]:
    """Get geographic location from IP address."""
    try:
        import geoip2.database
        reader = geoip2.database.Reader()
        response = reader.city(ip_address)
        
        return {
            'country': response.country.iso_code if response.country else 'unknown',
            'region': response.subdivisions.most_specific.iso_code if response.subdivisions else 'unknown',
            'city': response.city.name if response.city else 'unknown',
            'latitude': response.location.latitude if response.location else None,
            'longitude': response.location.longitude if response.location else None
        }
    except Exception as e:
        logger.warning(f"Geo lookup failed for IP {ip_address}: {e}")
        return None


def calculate_time_based_multiplier(
    current_hour: int,
    target_hours: List[int]
) -> float:
    """Calculate time-based multiplier for targeting."""
    if current_hour in target_hours:
        return 1.5  # Boost during target hours
    return 1.0


def calculate_behavioral_score(
    user_events: List[Dict[str, Any]],
    target_event_type: str,
    window_days: int = 30
) -> float:
    """Calculate behavioral score based on user events."""
    cutoff_date = timezone.now() - timedelta(days=window_days)
    
    relevant_events = [
        event for event in user_events
        if event.get('event_type') == target_event_type and
        event.get('created_at') >= cutoff_date
    ]
    
    if not relevant_events:
        return 0.0
    
    # Calculate frequency and recency scores
    total_events = len(relevant_events)
    frequency_score = min(total_events / 10, 1.0)  # Normalize to 0-1
    
    # Recency score (more recent events get higher score)
    if relevant_events:
        latest_event = max(event['created_at'] for event in relevant_events)
        days_since_latest = (timezone.now() - latest_event).days
        recency_score = max(1.0 - (days_since_latest / 30), 0.0)
    else:
        recency_score = 0.0
    
    # Combine scores
    behavioral_score = (frequency_score * 0.6) + (recency_score * 0.4)
    return min(behavioral_score * 100, 100.0)


def get_user_preference_vector(user_id: int) -> Dict[str, float]:
    """Get user preference vector from cache or database."""
    cache_key = f"{CACHE_PREFIX}:preference_vector:{user_id}"
    preference_vector = cache.get(cache_key)
    
    if preference_vector is None:
        # Load from database (placeholder)
        preference_vector = load_preference_vector_from_db(user_id)
        cache.set(cache_key, preference_vector, timeout=3600)  # 1 hour
    
    return preference_vector or {}


def load_preference_vector_from_db(user_id: int) -> Dict[str, float]:
    """Load preference vector from database."""
    # This would implement actual database query
    # For now, return empty dict
    return {}


def calculate_personalization_score(
    offer_categories: List[str],
    user_preference_vector: Dict[str, float]
) -> float:
    """Calculate personalization score based on user preferences."""
    if not user_preference_vector:
        return 0.0
    
    total_score = 0.0
    total_weight = 0.0
    
    for category in offer_categories:
        category_weight = user_preference_vector.get(category, 0.0)
        total_score += category_weight
        total_weight += 1.0
    
    if total_weight == 0:
        return 0.0
    
    return (total_score / total_weight) * 100


def apply_rate_limiting(
    user_id: int,
    action: str,
    limit: int,
    window_minutes: int = 60
) -> bool:
    """Check if user is within rate limit."""
    cache_key = f"{CACHE_PREFIX}:rate_limit:{user_id}:{action}"
    current_count = cache.get(cache_key, 0)
    
    if current_count >= limit:
        return False
    
    # Increment counter
    cache.set(cache_key, current_count + 1, timeout=window_minutes * 60)
    return True


def get_routing_performance_stats(
    route_id: int,
    time_window_hours: int = 24
) -> Dict[str, Any]:
    """Get routing performance statistics for a route."""
    # This would query analytics data
    # For now, return placeholder data
    return {
        'route_id': route_id,
        'time_window_hours': time_window_hours,
        'total_requests': 0,
        'avg_response_time_ms': 0,
        'success_rate': 0.0,
        'cache_hit_rate': 0.0
    }


def calculate_offer_exposure_stats(
    offer_id: int,
    time_window_hours: int = 24
) -> Dict[str, Any]:
    """Calculate offer exposure statistics."""
    # This would query analytics data
    return {
        'offer_id': offer_id,
        'time_window_hours': time_window_hours,
        'unique_users': 0,
        'total_shows': 0,
        'click_rate': 0.0,
        'conversion_rate': 0.0
    }


def sanitize_input(value: Any) -> Any:
    """Sanitize input for security."""
    if value is None:
        return None
    
    if isinstance(value, str):
        # Remove potentially dangerous characters
        value = value.strip()
        value = value.replace('<', '&lt;')
        value = value.replace('>', '&gt;')
        value = value.replace('"', '&quot;')
        value = value.replace("'", '&#x27;')
        return value
    
    return value


def validate_json_structure(data: Any, required_fields: List[str] = None) -> bool:
    """Validate JSON structure."""
    if not isinstance(data, dict):
        return False
    
    if required_fields:
        for field in required_fields:
            if field not in data:
                return False
    
    return True


def calculate_confidence_interval(
    values: List[float],
    confidence_level: float = 0.95
) -> Tuple[float, float]:
    """Calculate confidence interval for a list of values."""
    if not values:
        return (0.0, 0.0)
    
    import statistics
    mean = statistics.mean(values)
    std_dev = statistics.stdev(values) if len(values) > 1 else 0.0
    
    # Calculate margin of error
    from scipy import stats
    margin = stats.t.ppf((1 + confidence_level) / 2, len(values) - 1) * (std_dev / math.sqrt(len(values)))
    
    return (mean - margin, mean + margin)


def get_optimal_ranking_strategy(
    total_offers: int,
    user_segment: str = 'default'
) -> str:
    """Determine optimal ranking strategy based on context."""
    if total_offers <= 10:
        return RoutingStrategy.SCORE_BASED
    elif user_segment == 'premium':
        return RoutingStrategy.PERSONALIZATION_BASED
    else:
        return RoutingStrategy.HYBRID


def calculate_routing_quality_score(
    response_time_ms: float,
    cache_hit_rate: float,
    error_rate: float
) -> float:
    """Calculate overall routing quality score."""
    # Normalize each component to 0-100 scale
    time_score = max(0, 100 - (response_time_ms / MAX_ROUTING_TIME_MS * 100))
    cache_score = cache_hit_rate * 100
    error_score = max(0, 100 - (error_rate * 100))
    
    # Weighted average
    quality_score = (time_score * 0.4) + (cache_score * 0.3) + (error_score * 0.3)
    return quality_score


def format_routing_decision(decision_data: Dict[str, Any]) -> Dict[str, Any]:
    """Format routing decision for logging."""
    return {
        'timestamp': timezone.now().isoformat(),
        'user_id': decision_data.get('user_id'),
        'route_id': decision_data.get('route_id'),
        'offer_ids': decision_data.get('offer_ids', []),
        'scores': decision_data.get('scores', {}),
        'reason': decision_data.get('reason'),
        'response_time_ms': decision_data.get('response_time_ms'),
        'cache_hit': decision_data.get('cache_hit', False),
        'personalization_applied': decision_data.get('personalization_applied', False),
        'caps_checked': decision_data.get('caps_checked', False),
        'fallback_used': decision_data.get('fallback_used', False)
    }


def get_user_segment_info(user_id: int) -> Dict[str, Any]:
    """Get comprehensive user segment information."""
    # This would query user data and behavioral history
    # For now, return placeholder data
    return {
        'user_id': user_id,
        'tier': 'basic',
        'is_new_user': False,
        'is_active_user': True,
        'is_churned_user': False,
        'is_premium_user': False,
        'is_engaged_user': True,
        'is_inactive_user': False,
        'days_since_signup': 30,
        'last_activity': timezone.now() - timedelta(days=1),
        'total_purchases': 5,
        'total_sessions': 50,
        'avg_session_duration': 15.5
    }


def calculate_ab_test_sample_size(
    baseline_cr: float,
    minimum_detectable_effect: float = 0.02,
    power: float = 0.8,
    significance_level: float = 0.95
) -> int:
    """Calculate required sample size for A/B test."""
    from scipy import stats
    import math
    
    # Calculate Z-scores
    z_alpha = stats.norm.ppf(1 - (1 - significance_level) / 2)
    z_beta = stats.norm.ppf(power)
    
    # Calculate sample size
    p1 = baseline_cr
    p2 = baseline_cr + minimum_detectable_effect
    
    if p1 <= 0 or p1 >= 1 or p2 <= 0 or p2 >= 1:
        return 1000  # Default minimum
    
    sample_size = (
        (z_alpha * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2)) +
         z_beta * math.sqrt((p1 + p2) * (1 - (p1 + p2) / 2)))
    ) ** 2 / (p2 - p1) ** 2
    
    return max(int(sample_size), 1000)


def get_fallback_offers(
    tenant_id: int,
    fallback_type: str,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """Get fallback offers based on type."""
    # This would query fallback rules and return appropriate offers
    # For now, return empty list
    return []


def log_routing_performance(
    route_id: int,
    user_id: int,
    response_time_ms: float,
    success: bool,
    cache_hit: bool = False,
    error_message: str = None
) -> None:
    """Log routing performance for analytics."""
    log_data = {
        'timestamp': timezone.now(),
        'route_id': route_id,
        'user_id': user_id,
        'response_time_ms': response_time_ms,
        'success': success,
        'cache_hit': cache_hit,
        'error_message': error_message
    }
    
    # Log to analytics system
    logger.info(f"Routing performance: {json.dumps(log_data)}")
    
    # Store in performance stats table
    # This would implement actual database storage


def warm_routing_cache(user_ids: List[int]) -> None:
    """Warm routing cache for specified users."""
    for user_id in user_ids:
        # Pre-warm cache with common contexts
        common_contexts = [
            {'page': 'home'},
            {'page': 'products'},
            {'page': 'offers'},
            {'page': 'profile'}
        ]
        
        for context in common_contexts:
            context_hash = hash_context(context)
            cache_key = get_routing_cache_key(user_id, context_hash)
            
            # Set empty cache entry to warm up
            cache.set(cache_key, {}, timeout=60)


def cleanup_expired_cache_entries() -> int:
    """Clean up expired cache entries."""
    # This would implement cache cleanup logic
    # For now, return count of cleaned entries
    return 0


def get_routing_config(tenant_id: int) -> Dict[str, Any]:
    """Get routing configuration for tenant."""
    cache_key = f"{CACHE_PREFIX}:routing_config:{tenant_id}"
    config = cache.get(cache_key)
    
    if config is None:
        # Load from database
        config = load_routing_config_from_db(tenant_id)
        cache.set(cache_key, config, timeout=3600)  # 1 hour
    
    return config or {}


def load_routing_config_from_db(tenant_id: int) -> Dict[str, Any]:
    """Load routing configuration from database."""
    # This would implement actual database query
    # For now, return default config
    return {
        'max_routing_time_ms': MAX_ROUTING_TIME_MS,
        'cache_enabled': True,
        'personalization_enabled': True,
        'ab_testing_enabled': True,
        'diversity_rules': {
            'max_per_category': 3,
            'max_per_merchant': 2
        }
    }


def validate_routing_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate routing request data. Returns cleaned data or raises ValueError."""
    if not isinstance(data, dict):
        raise ValueError("Routing data must be a dictionary")
    return data


def format_routing_response(routes, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """Format routing results into a standard API response."""
    return {
        'routes': routes if isinstance(routes, list) else list(routes),
        'count': len(routes) if hasattr(routes, '__len__') else 0,
        'metadata': metadata or {},
    }
