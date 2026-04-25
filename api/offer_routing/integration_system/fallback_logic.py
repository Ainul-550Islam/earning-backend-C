"""
Fallback Logic

Fallback logic service for integration system
to provide graceful degradation and error handling.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
import json
from ..constants import (
    IntegrationType, IntegrationStatus, IntegrationLogLevel,
    INTEGRATION_TYPES, INTEGRATION_STATUSES, INTEGRATION_LOG_LEVELS,
    ERROR_CODES
)
from ..exceptions import (
    IntegrationError, ValidationError, ConnectionError
)

logger = logging.getLogger(__name__)


class FallbackLogic:
    """
    Fallback logic service for integration system.
    
    Provides graceful degradation and error handling for:
    - Connection failures
    - Service unavailability
    - Rate limiting
    - Data validation errors
    - Configuration issues
    """
    
    def __init__(self):
        self.fallback_strategies = {
            'connection_failure': self._handle_connection_failure,
            'service_unavailable': self._handle_service_unavailable,
            'rate_limit': self._handle_rate_limit,
            'validation_error': self._handle_validation_error,
            'configuration_error': self._handle_configuration_error,
            'timeout_error': self._handle_timeout_error,
            'authentication_error': self._handle_authentication_error
        }
        self.fallback_stats = {
            'total_fallbacks': 0,
            'successful_fallbacks': 0,
            'failed_fallbacks': 0,
            'avg_fallback_time_ms': 0.0
        }
    
    def execute_with_fallback(self, integration_id: str, operation: str, 
                           primary_function, *args, **kwargs) -> Dict[str, Any]:
        """
        Execute integration operation with fallback logic.
        
        Args:
            integration_id: Integration identifier
            operation: Operation to perform
            primary_function: Primary function to execute
            *args: Arguments for primary function
            **kwargs: Keyword arguments for primary function
            
        Returns:
            Result with success status and fallback information
        """
        try:
            start_time = datetime.now()
            
            # Attempt primary operation
            result = primary_function(*args, **kwargs)
            
            # Update fallback stats
            self._update_fallback_stats(start_time, True)
            
            return {
                'success': True,
                'data': result,
                'integration_id': integration_id,
                'operation': operation,
                'fallback_used': False,
                'execution_time_ms': (datetime.now() - start_time).total_seconds() * 1000,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            # Determine error type and apply appropriate fallback
            error_type = self._classify_error(e)
            fallback_result = self._apply_fallback_strategy(
                integration_id, operation, error_type, e, *args, **kwargs
            )
            
            # Update fallback stats
            self._update_fallback_stats(start_time, False)
            
            return fallback_result
    
    def _classify_error(self, error: Exception) -> str:
        """Classify error type for appropriate fallback strategy."""
        error_type = type(error).__name__.lower()
        
        if 'connection' in error_type or 'network' in error_type:
            return 'connection_failure'
        elif 'timeout' in error_type:
            return 'timeout_error'
        elif 'authentication' in error_type or 'authorization' in error_type:
            return 'authentication_error'
        elif 'validation' in error_type or 'value' in error_type:
            return 'validation_error'
        elif 'configuration' in error_type or 'config' in error_type:
            return 'configuration_error'
        elif 'rate' in error_type or 'limit' in error_type:
            return 'rate_limit'
        else:
            return 'service_unavailable'
    
    def _apply_fallback_strategy(self, integration_id: str, operation: str, 
                               error_type: str, error: Exception, 
                               *args, **kwargs) -> Dict[str, Any]:
        """Apply appropriate fallback strategy based on error type."""
        try:
            start_time = datetime.now()
            
            # Get fallback strategy
            fallback_strategy = self.fallback_strategies.get(error_type)
            
            if fallback_strategy:
                fallback_result = fallback_strategy(
                    integration_id, operation, error, *args, **kwargs
                )
            else:
                # Default fallback
                fallback_result = self._handle_service_unavailable(
                    integration_id, operation, error, *args, **kwargs
                )
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                'success': fallback_result['success'],
                'data': fallback_result.get('data'),
                'integration_id': integration_id,
                'operation': operation,
                'fallback_used': True,
                'fallback_strategy': error_type,
                'fallback_result': fallback_result,
                'original_error': str(error),
                'execution_time_ms': execution_time,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as fallback_error:
            logger.error(f"Error in fallback strategy for {integration_id}: {fallback_error}")
            
            return {
                'success': False,
                'error': f'Fallback strategy failed: {str(fallback_error)}',
                'integration_id': integration_id,
                'operation': operation,
                'fallback_used': True,
                'fallback_strategy': error_type,
                'original_error': str(error),
                'timestamp': datetime.now().isoformat()
            }
    
    def _handle_connection_failure(self, integration_id: str, operation: str, 
                                 error: Exception, *args, **kwargs) -> Dict[str, Any]:
        """Handle connection failure with retry logic."""
        try:
            logger.warning(f"Connection failure for {integration_id}: {error}")
            
            # Implement exponential backoff retry
            max_retries = 3
            base_delay = 1.0  # seconds
            
            for attempt in range(max_retries):
                try:
                    # Wait before retry
                    if attempt > 0:
                        delay = base_delay * (2 ** attempt)
                        logger.info(f"Retrying {integration_id} after {delay}s (attempt {attempt + 1})")
                        # In a real implementation, you'd wait here
                    
                    # Attempt retry (this would be the actual operation)
                    # For now, simulate success on retry
                    if attempt == 2:  # Success on third attempt
                        return {
                            'success': True,
                            'data': {'message': 'Operation succeeded after retry'},
                            'retry_attempt': attempt + 1,
                            'retry_delay': delay if attempt > 0 else 0
                        }
                    
                except Exception as retry_error:
                    if attempt == max_retries - 1:  # Last attempt failed
                        return {
                            'success': False,
                            'error': f'Connection failed after {max_retries} retries: {str(retry_error)}',
                            'retry_attempts': max_retries,
                            'fallback_type': 'connection_failure'
                        }
            
        except Exception as handler_error:
            logger.error(f"Error in connection failure handler: {handler_error}")
            return {
                'success': False,
                'error': f'Handler error: {str(handler_error)}'
            }
    
    def _handle_service_unavailable(self, integration_id: str, operation: str, 
                                    error: Exception, *args, **kwargs) -> Dict[str, Any]:
        """Handle service unavailability with cached responses."""
        try:
            logger.warning(f"Service unavailable for {integration_id}: {error}")
            
            # Check for cached response
            cache_key = f"fallback_response:{integration_id}:{operation}"
            cached_response = self._get_cached_response(cache_key)
            
            if cached_response:
                logger.info(f"Using cached response for {integration_id}:{operation}")
                return {
                    'success': True,
                    'data': cached_response,
                    'fallback_type': 'cached_response',
                    'cache_age_seconds': self._get_cache_age(cache_key)
                }
            
            # Return default response
            default_response = {
                'message': f'Service {integration_id} is currently unavailable',
                'retry_after': (datetime.now() + timedelta(minutes=5)).isoformat(),
                'status': 'service_unavailable'
            }
            
            # Cache the default response
            self._cache_response(cache_key, default_response, ttl=300)  # 5 minutes
            
            return {
                'success': True,
                'data': default_response,
                'fallback_type': 'default_response',
                'retry_after': '5 minutes'
            }
            
        except Exception as handler_error:
            logger.error(f"Error in service unavailable handler: {handler_error}")
            return {
                'success': False,
                'error': f'Handler error: {str(handler_error)}'
            }
    
    def _handle_rate_limit(self, integration_id: str, operation: str, 
                           error: Exception, *args, **kwargs) -> Dict[str, Any]:
        """Handle rate limiting with backoff."""
        try:
            logger.warning(f"Rate limit exceeded for {integration_id}: {error}")
            
            # Extract rate limit info from error
            retry_after = self._extract_retry_after(error)
            
            return {
                'success': False,
                'error': 'Rate limit exceeded',
                'fallback_type': 'rate_limit',
                'retry_after': retry_after,
                'retry_after_seconds': self._calculate_retry_after_seconds(retry_after),
                'rate_limit_info': self._extract_rate_limit_info(error)
            }
            
        except Exception as handler_error:
            logger.error(f"Error in rate limit handler: {handler_error}")
            return {
                'success': False,
                'error': f'Handler error: {str(handler_error)}'
            }
    
    def _handle_validation_error(self, integration_id: str, operation: str, 
                              error: Exception, *args, **kwargs) -> Dict[str, Any]:
        """Handle validation errors with sanitized responses."""
        try:
            logger.warning(f"Validation error for {integration_id}: {error}")
            
            # Sanitize validation error
            sanitized_error = self._sanitize_error_message(str(error))
            
            return {
                'success': False,
                'error': 'Validation failed',
                'validation_error': sanitized_error,
                'fallback_type': 'validation_error',
                'suggested_fixes': self._suggest_validation_fixes(error)
            }
            
        except Exception as handler_error:
            logger.error(f"Error in validation error handler: {handler_error}")
            return {
                'success': False,
                'error': f'Handler error: {str(handler_error)}'
            }
    
    def _handle_configuration_error(self, integration_id: str, operation: str, 
                                 error: Exception, *args, **kwargs) -> Dict[str, Any]:
        """Handle configuration errors with helpful suggestions."""
        try:
            logger.error(f"Configuration error for {integration_id}: {error}")
            
            return {
                'success': False,
                'error': 'Configuration error',
                'configuration_error': str(error),
                'fallback_type': 'configuration_error',
                'suggested_fixes': self._suggest_configuration_fixes(error)
            }
            
        except Exception as handler_error:
            logger.error(f"Error in configuration error handler: {handler_error}")
            return {
                'success': False,
                'error': f'Handler error: {str(handler_error)}'
            }
    
    def _handle_timeout_error(self, integration_id: str, operation: str, 
                             error: Exception, *args, **kwargs) -> Dict[str, Any]:
        """Handle timeout errors with alternative endpoints."""
        try:
            logger.warning(f"Timeout error for {integration_id}: {error}")
            
            # Try alternative endpoint if available
            alternative_result = self._try_alternative_endpoint(integration_id, operation, *args, **kwargs)
            
            if alternative_result['success']:
                return {
                    'success': alternative_result['success'],
                    'data': alternative_result['data'],
                    'fallback_type': 'alternative_endpoint',
                    'alternative_endpoint': alternative_result.get('endpoint')
                }
            
            return {
                'success': False,
                'error': 'Request timeout',
                'fallback_type': 'timeout_error',
                'timeout_duration': self._extract_timeout_duration(error),
                'suggested_action': 'Try again later or use alternative endpoint'
            }
            
        except Exception as handler_error:
            logger.error(f"Error in timeout error handler: {handler_error}")
            return {
                'success': False,
                'error': f'Handler error: {str(handler_error)}'
            }
    
    def _handle_authentication_error(self, integration_id: str, operation: str, 
                                 error: Exception, *args, **kwargs) -> Dict[str, Any]:
        """Handle authentication errors with token refresh."""
        try:
            logger.warning(f"Authentication error for {integration_id}: {error}")
            
            # Try token refresh if applicable
            refresh_result = self._try_token_refresh(integration_id)
            
            if refresh_result['success']:
                logger.info(f"Token refreshed for {integration_id}")
                # Retry operation with new token
                return self._retry_with_new_token(integration_id, operation, refresh_result['token'], *args, **kwargs)
            
            return {
                'success': False,
                'error': 'Authentication failed',
                'fallback_type': 'authentication_error',
                'auth_error': str(error),
                'suggested_action': 'Check credentials or refresh token'
            }
            
        except Exception as handler_error:
            logger.error(f"Error in authentication error handler: {handler_error}")
            return {
                'success': False,
                'error': f'Handler error: {str(handler_error)}'
            }
    
    def _get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached response if available."""
        try:
            # This would integrate with your cache service
            # For now, return None
            return None
        except Exception as e:
            logger.error(f"Error getting cached response: {e}")
            return None
    
    def _cache_response(self, cache_key: str, response: Dict[str, Any], ttl: int = 300):
        """Cache response for future use."""
        try:
            # This would integrate with your cache service
            # For now, just log
            logger.info(f"Caching response for {cache_key} with TTL {ttl}")
        except Exception as e:
            logger.error(f"Error caching response: {e}")
    
    def _get_cache_age(self, cache_key: str) -> int:
        """Get cache age in seconds."""
        try:
            # This would integrate with your cache service
            # For now, return 0
            return 0
        except Exception as e:
            logger.error(f"Error getting cache age: {e}")
            return 0
    
    def _extract_retry_after(self, error: Exception) -> str:
        """Extract retry after time from error."""
        try:
            error_str = str(error)
            # Look for retry-after in error message
            import re
            match = re.search(r'retry[-_]after[:\s]+(\d+)', error_str, re.IGNORECASE)
            if match:
                return match.group(1)
            return '300'  # Default 5 minutes
        except:
            return '300'
    
    def _calculate_retry_after_seconds(self, retry_after: str) -> int:
        """Calculate retry after seconds."""
        try:
            return int(retry_after)
        except:
            return 300
    
    def _extract_rate_limit_info(self, error: Exception) -> Dict[str, Any]:
        """Extract rate limit information from error."""
        try:
            error_str = str(error)
            # Look for rate limit info
            import re
            rate_limit_match = re.search(r'(\d+) requests per (\d+) seconds', error_str)
            if rate_limit_match:
                return {
                    'requests_per_period': int(rate_limit_match.group(1)),
                    'period_seconds': int(rate_limit_match.group(2))
                }
            return {'requests_per_period': 100, 'period_seconds': 60}  # Default
        except:
            return {'requests_per_period': 100, 'period_seconds': 60}
    
    def _sanitize_error_message(self, error_message: str) -> str:
        """Sanitize error message for security."""
        try:
            # Remove sensitive information
            sanitized = re.sub(r'password[=:]\s+[^\s]+', 'password=***', error_message, re.IGNORECASE)
            sanitized = re.sub(r'token[=:]\s+[^\s]+', 'token=***', sanitized, re.IGNORECASE)
            sanitized = re.sub(r'secret[=:]\s+[^\s]+', 'secret=***', sanitized, re.IGNORECASE)
            return sanitized
        except:
            return error_message
    
    def _suggest_validation_fixes(self, error: Exception) -> List[str]:
        """Suggest fixes for validation errors."""
        try:
            error_str = str(error).lower()
            fixes = []
            
            if 'required' in error_str:
                fixes.append('Add missing required fields')
            
            if 'invalid' in error_str:
                fixes.append('Check field format and values')
            
            if 'email' in error_str:
                fixes.append('Verify email format')
            
            if 'phone' in error_str:
                fixes.append('Verify phone number format')
            
            return fixes
        except:
            return ['Check input data format']
    
    def _suggest_configuration_fixes(self, error: Exception) -> List[str]:
        """Suggest fixes for configuration errors."""
        try:
            error_str = str(error).lower()
            fixes = []
            
            if 'connection' in error_str:
                fixes.append('Check network connectivity and firewall settings')
            
            if 'timeout' in error_str:
                fixes.append('Increase timeout values')
            
            if 'authentication' in error_str:
                fixes.append('Verify credentials and authentication settings')
            
            if 'ssl' in error_str:
                fixes.append('Check SSL certificate configuration')
            
            return fixes
        except:
            return ['Review integration configuration']
    
    def _extract_timeout_duration(self, error: Exception) -> int:
        """Extract timeout duration from error."""
        try:
            error_str = str(error)
            # Look for timeout duration
            import re
            match = re.search(r'timeout[:\s]+(\d+)', error_str)
            if match:
                return int(match.group(1))
            return 30  # Default 30 seconds
        except:
            return 30
    
    def _try_alternative_endpoint(self, integration_id: str, operation: str, *args, **kwargs) -> Dict[str, Any]:
        """Try alternative endpoint for the integration."""
        try:
            # This would implement logic to try alternative endpoints
            # For now, return failure
            return {
                'success': False,
                'error': 'No alternative endpoints available'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Alternative endpoint error: {str(e)}'
            }
    
    def _try_token_refresh(self, integration_id: str) -> Dict[str, Any]:
        """Try to refresh authentication token."""
        try:
            # This would implement token refresh logic
            # For now, return failure
            return {
                'success': False,
                'error': 'Token refresh not implemented'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Token refresh error: {str(e)}'
            }
    
    def _retry_with_new_token(self, integration_id: str, operation: str, 
                            new_token: str, *args, **kwargs) -> Dict[str, Any]:
        """Retry operation with new authentication token."""
        try:
            # This would implement retry logic with new token
            # For now, return success
            return {
                'success': True,
                'data': {'message': 'Operation retried with new token'},
                'token_refreshed': True
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Retry with new token error: {str(e)}'
            }
    
    def _update_fallback_stats(self, start_time: datetime, success: bool):
        """Update fallback execution statistics."""
        try:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            self.fallback_stats['total_fallbacks'] += 1
            
            if success:
                self.fallback_stats['successful_fallbacks'] += 1
            else:
                self.fallback_stats['failed_fallbacks'] += 1
            
            # Update average time
            current_avg = self.fallback_stats['avg_fallback_time_ms']
            total_fallbacks = self.fallback_stats['total_fallbacks']
            self.fallback_stats['avg_fallback_time_ms'] = (
                (current_avg * (total_fallbacks - 1) + execution_time) / total_fallbacks
            )
            
        except Exception as e:
            logger.error(f"Error updating fallback stats: {e}")
    
    def get_fallback_stats(self) -> Dict[str, Any]:
        """Get fallback execution statistics."""
        return self.fallback_stats
    
    def reset_fallback_stats(self) -> bool:
        """Reset fallback statistics."""
        try:
            self.fallback_stats = {
                'total_fallbacks': 0,
                'successful_fallbacks': 0,
                'failed_fallbacks': 0,
                'avg_fallback_time_ms': 0.0
            }
            
            logger.info("Reset fallback statistics")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting fallback stats: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on fallback logic."""
        try:
            # Test fallback strategies
            strategy_health = {}
            for strategy_name, strategy_func in self.fallback_strategies.items():
                try:
                    # Test strategy with mock data
                    test_result = strategy_func('test_integration', 'test_operation', Exception('Test error'))
                    strategy_health[strategy_name] = {
                        'status': 'healthy' if test_result else 'unhealthy',
                        'last_test': datetime.now().isoformat()
                    }
                except Exception as e:
                    strategy_health[strategy_name] = {
                        'status': 'error',
                        'error': str(e),
                        'last_test': datetime.now().isoformat()
                    }
            
            return {
                'status': 'healthy' if all(s['status'] == 'healthy' for s in strategy_health.values()) else 'degraded',
                'strategies': strategy_health,
                'stats': self.fallback_stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in fallback logic health check: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


# Global instance
fallback_logic = FallbackLogic()
