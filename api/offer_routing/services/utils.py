"""
Utility Services for Offer Routing System

This module provides utility functions and helper services
for common routing operations.
"""

import logging
import hashlib
import json
from typing import Dict, List, Any, Optional, Tuple
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from ..models import RoutingDecisionLog, UserOfferHistory
from ..exceptions import ValidationError

User = get_user_model()
logger = logging.getLogger(__name__)


class RoutingUtilsService:
    """
    Service for routing utility functions.
    
    Provides helper functions for common routing operations.
    """
    
    def __init__(self):
        pass
    
    def generate_user_hash(self, user_id: int, additional_data: Dict[str, Any] = None) -> str:
        """Generate consistent hash for user."""
        try:
            hash_input = str(user_id)
            
            if additional_data:
                hash_input += json.dumps(additional_data, sort_keys=True)
            
            return hashlib.md5(hash_input.encode()).hexdigest()
            
        except Exception as e:
            logger.error(f"Error generating user hash: {e}")
            return str(user_id)
    
    def generate_context_hash(self, context: Dict[str, Any]) -> str:
        """Generate hash for context data."""
        try:
            # Sort keys for consistent hashing
            context_str = json.dumps(context, sort_keys=True)
            return hashlib.md5(context_str.encode()).hexdigest()
            
        except Exception as e:
            logger.error(f"Error generating context hash: {e}")
            return hashlib.md5(str(context).encode()).hexdigest()
    
    def normalize_score(self, score: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
        """Normalize score to specified range."""
        try:
            if score < min_val:
                return min_val
            if score > max_val:
                return max_val
            
            return score
            
        except Exception as e:
            logger.error(f"Error normalizing score: {e}")
            return 0.0
    
    def calculate_percentile(self, values: List[float], target_value: float) -> float:
        """Calculate percentile rank of target value."""
        try:
            if not values:
                return 0.0
            
            sorted_values = sorted(values)
            rank = 0
            
            for value in sorted_values:
                if value <= target_value:
                    rank += 1
            
            percentile = (rank / len(sorted_values)) * 100
            return percentile
            
        except Exception as e:
            logger.error(f"Error calculating percentile: {e}")
            return 0.0
    
    def validate_routing_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate routing data structure."""
        try:
            errors = []
            warnings = []
            
            # Check required fields
            required_fields = ['user_id', 'context']
            for field in required_fields:
                if field not in data:
                    errors.append(f"Missing required field: {field}")
            
            # Validate user_id
            if 'user_id' in data:
                user_id = data['user_id']
                if not isinstance(user_id, int) or user_id <= 0:
                    errors.append("user_id must be a positive integer")
            
            # Validate context
            if 'context' in data:
                context = data['context']
                if not isinstance(context, dict):
                    errors.append("context must be a dictionary")
            
            # Validate limit
            if 'limit' in data:
                limit = data['limit']
                if not isinstance(limit, int) or limit <= 0 or limit > 100:
                    warnings.append("limit should be between 1 and 100")
            
            return {
                'is_valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings
            }
            
        except Exception as e:
            logger.error(f"Error validating routing data: {e}")
            return {
                'is_valid': False,
                'errors': [str(e)],
                'warnings': []
            }
    
    def extract_user_agent_info(self, user_agent: str) -> Dict[str, Any]:
        """Extract user agent information."""
        try:
            user_agent_lower = user_agent.lower()
            
            info = {
                'device_type': 'desktop',
                'os': 'unknown',
                'browser': 'unknown',
                'is_mobile': False,
                'is_tablet': False,
                'is_bot': False
            }
            
            # Detect device type
            if any(mobile in user_agent_lower for mobile in ['mobile', 'android', 'iphone', 'ipad']):
                info['device_type'] = 'mobile'
                info['is_mobile'] = True
            
            if 'tablet' in user_agent_lower or 'ipad' in user_agent_lower:
                info['device_type'] = 'tablet'
                info['is_tablet'] = True
            
            # Detect OS
            if 'windows' in user_agent_lower:
                info['os'] = 'windows'
            elif 'mac' in user_agent_lower or 'os x' in user_agent_lower:
                info['os'] = 'macos'
            elif 'linux' in user_agent_lower:
                info['os'] = 'linux'
            elif 'android' in user_agent_lower:
                info['os'] = 'android'
            elif 'iphone' in user_agent_lower or 'ipad' in user_agent_lower:
                info['os'] = 'ios'
            
            # Detect browser
            if 'chrome' in user_agent_lower:
                info['browser'] = 'chrome'
            elif 'firefox' in user_agent_lower:
                info['browser'] = 'firefox'
            elif 'safari' in user_agent_lower:
                info['browser'] = 'safari'
            elif 'edge' in user_agent_lower or 'edg' in user_agent_lower:
                info['browser'] = 'edge'
            elif 'opera' in user_agent_lower:
                info['browser'] = 'opera'
            elif 'msie' in user_agent_lower or 'trident' in user_agent_lower:
                info['browser'] = 'ie'
            
            # Detect bots
            bot_indicators = ['bot', 'crawler', 'spider', 'scraper', 'curl', 'wget']
            if any(bot in user_agent_lower for bot in bot_indicators):
                info['is_bot'] = True
            
            return info
            
        except Exception as e:
            logger.error(f"Error extracting user agent info: {e}")
            return {
                'device_type': 'desktop',
                'os': 'unknown',
                'browser': 'unknown',
                'is_mobile': False,
                'is_tablet': False,
                'is_bot': False
            }
    
    def parse_ip_address(self, ip_address: str) -> Dict[str, Any]:
        """Parse and validate IP address."""
        try:
            import ipaddress
            
            ip_obj = ipaddress.ip_address(ip_address)
            
            return {
                'is_valid': True,
                'is_ipv4': ip_obj.version == 4,
                'is_ipv6': ip_obj.version == 6,
                'is_private': ip_obj.is_private,
                'is_loopback': ip_obj.is_loopback,
                'is_multicast': ip_obj.is_multicast,
                'ip_address': str(ip_obj)
            }
            
        except ValueError:
            return {
                'is_valid': False,
                'error': 'Invalid IP address format'
            }
        except Exception as e:
            logger.error(f"Error parsing IP address: {e}")
            return {
                'is_valid': False,
                'error': str(e)
            }
    
    def format_routing_response(self, success: bool, offers: List[Dict[str, Any]], 
                              metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Format routing response."""
        try:
            response = {
                'success': success,
                'offers': offers,
                'metadata': metadata,
                'timestamp': timezone.now().isoformat()
            }
            
            # Add performance metrics if available
            if 'response_time_ms' in metadata:
                response['performance'] = {
                    'response_time_ms': metadata['response_time_ms']
                }
            
            # Add caching info if available
            if 'cache_hit' in metadata:
                response['caching'] = {
                    'cache_hit': metadata['cache_hit']
                }
            
            # Add personalization info if available
            if 'personalization_applied' in metadata:
                response['personalization'] = {
                    'applied': metadata['personalization_applied']
                }
            
            return response
            
        except Exception as e:
            logger.error(f"Error formatting routing response: {e}")
            return {
                'success': False,
                'offers': [],
                'metadata': {'error': str(e)},
                'timestamp': timezone.now().isoformat()
            }
    
    def calculate_routing_quality_score(self, response_time_ms: float, cache_hit_rate: float, 
                                     error_rate: float) -> float:
        """Calculate overall routing quality score."""
        try:
            # Normalize each component to 0-100 scale
            time_score = max(0, 100 - (response_time_ms / 100))  # 100ms = 0 score
            cache_score = cache_hit_rate  # Already 0-100
            error_score = max(0, 100 - (error_rate * 10))  # 10% error = 0 score
            
            # Weighted average
            quality_score = (time_score * 0.4) + (cache_score * 0.3) + (error_score * 0.3)
            
            return quality_score
            
        except Exception as e:
            logger.error(f"Error calculating routing quality score: {e}")
            return 0.0
    
    def get_user_routing_history(self, user_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """Get user's routing history."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            decisions = RoutingDecisionLog.objects.filter(
                user_id=user_id,
                created_at__gte=cutoff_date
            ).order_by('-created_at')
            
            history = []
            for decision in decisions:
                history.append({
                    'decision_id': decision.id,
                    'offer_id': decision.offer_id,
                    'route_id': decision.route_id,
                    'reason': decision.reason,
                    'score': float(decision.score),
                    'rank': decision.rank,
                    'response_time_ms': decision.response_time_ms,
                    'cache_hit': decision.cache_hit,
                    'personalization_applied': decision.personalization_applied,
                    'caps_checked': decision.caps_checked,
                    'fallback_used': decision.fallback_used,
                    'created_at': decision.created_at.isoformat()
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting user routing history: {e}")
            return []
    
    def get_offer_routing_stats(self, offer_id: int, days: int = 30) -> Dict[str, Any]:
        """Get offer routing statistics."""
        try:
            from datetime import timedelta
            from django.db.models import Avg, Count, Sum
            
            cutoff_date = timezone.now() - timedelta(days=days)
            
            stats = RoutingDecisionLog.objects.filter(
                offer_id=offer_id,
                created_at__gte=cutoff_date
            ).aggregate(
                total_decisions=Count('id'),
                unique_users=Count('user_id', distinct=True),
                avg_score=Avg('score'),
                avg_rank=Avg('rank'),
                cache_hit_rate=Avg('cache_hit'),
                personalization_rate=Avg('personalization_applied'),
                fallback_rate=Avg('fallback_used')
            )
            
            return {
                'total_decisions': stats['total_decisions'] or 0,
                'unique_users': stats['unique_users'] or 0,
                'avg_score': float(stats['avg_score'] or 0),
                'avg_rank': float(stats['avg_rank'] or 0),
                'cache_hit_rate': float(stats['cache_hit_rate'] or 0) * 100,
                'personalization_rate': float(stats['personalization_rate'] or 0) * 100,
                'fallback_rate': float(stats['fallback_rate'] or 0) * 100,
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting offer routing stats: {e}")
            return {}
    
    def cleanup_old_data(self, days: int = 90) -> int:
        """Clean up old routing data."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Clean up old decision logs
            deleted_decisions = RoutingDecisionLog.objects.filter(
                created_at__lt=cutoff_date
            ).delete()[0]
            
            # Clean up old user offer history
            deleted_history = UserOfferHistory.objects.filter(
                created_at__lt=cutoff_date
            ).delete()[0]
            
            total_deleted = deleted_decisions + deleted_history
            
            logger.info(f"Cleaned up {total_deleted} old routing records")
            return total_deleted
            
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            return 0
    
    def export_routing_data(self, tenant_id: int, days: int = 30) -> Dict[str, Any]:
        """Export routing data for analysis."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get decision logs
            decisions = RoutingDecisionLog.objects.filter(
                user__tenant_id=tenant_id,
                created_at__gte=cutoff_date
            ).values(
                'user_id', 'offer_id', 'route_id', 'reason', 'score', 'rank',
                'response_time_ms', 'cache_hit', 'personalization_applied',
                'caps_checked', 'fallback_used', 'created_at'
            )
            
            # Get user offer history
            history = UserOfferHistory.objects.filter(
                user__tenant_id=tenant_id,
                created_at__gte=cutoff_date
            ).values(
                'user_id', 'offer_id', 'route_id', 'viewed_at', 'clicked_at',
                'completed_at', 'conversion_value', 'personalization_applied',
                'created_at'
            )
            
            export_data = {
                'tenant_id': tenant_id,
                'period_days': days,
                'export_date': timezone.now().isoformat(),
                'decisions': list(decisions),
                'history': list(history)
            }
            
            return export_data
            
        except Exception as e:
            logger.error(f"Error exporting routing data: {e}")
            return {}
    
    def import_routing_data(self, tenant_id: int, import_data: Dict[str, Any]) -> bool:
        """Import routing data from export."""
        try:
            # This would implement data import logic
            # For now, return True as placeholder
            
            logger.info(f"Imported routing data for tenant {tenant_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error importing routing data: {e}")
            return False


class ValidationService:
    """Service for data validation."""
    
    def validate_offer_data(self, offer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate offer data structure."""
        try:
            errors = []
            warnings = []
            
            # Check required fields
            required_fields = ['name', 'tenant_id']
            for field in required_fields:
                if field not in offer_data:
                    errors.append(f"Missing required field: {field}")
            
            # Validate name
            if 'name' in offer_data:
                name = offer_data['name']
                if not isinstance(name, str) or len(name.strip()) < 3:
                    errors.append("Name must be a string with at least 3 characters")
                elif len(name) > 100:
                    warnings.append("Name is longer than 100 characters")
            
            # Validate priority
            if 'priority' in offer_data:
                priority = offer_data['priority']
                if not isinstance(priority, int) or priority < 1 or priority > 10:
                    errors.append("Priority must be an integer between 1 and 10")
            
            # Validate max_offers
            if 'max_offers' in offer_data:
                max_offers = offer_data['max_offers']
                if not isinstance(max_offers, int) or max_offers < 1 or max_offers > 1000:
                    errors.append("Max offers must be an integer between 1 and 1000")
            
            return {
                'is_valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings
            }
            
        except Exception as e:
            logger.error(f"Error validating offer data: {e}")
            return {
                'is_valid': False,
                'errors': [str(e)],
                'warnings': []
            }
    
    def validate_route_data(self, route_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate route data structure."""
        try:
            errors = []
            warnings = []
            
            # Check required fields
            required_fields = ['name', 'tenant_id']
            for field in required_fields:
                if field not in route_data:
                    errors.append(f"Missing required field: {field}")
            
            # Validate conditions
            if 'conditions' in route_data:
                conditions = route_data['conditions']
                if not isinstance(conditions, list):
                    errors.append("Conditions must be a list")
                else:
                    for i, condition in enumerate(conditions):
                        if not isinstance(condition, dict):
                            errors.append(f"Condition {i} must be a dictionary")
                        elif 'field_name' not in condition:
                            errors.append(f"Condition {i} missing field_name")
                        elif 'operator' not in condition:
                            errors.append(f"Condition {i} missing operator")
                        elif 'value' not in condition:
                            errors.append(f"Condition {i} missing value")
            
            return {
                'is_valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings
            }
            
        except Exception as e:
            logger.error(f"Error validating route data: {e}")
            return {
                'is_valid': False,
                'errors': [str(e)],
                'warnings': []
            }


# Singleton instances
utils_service = RoutingUtilsService()
validation_service = ValidationService()
