# =============================================================================
# INTEGRATION_SYSTEM/fallback_logic.py
# =============================================================================
"""
Fallback Logic for Integration Failures.

Provides comprehensive fallback mechanisms for integration failures
including alternative methods, cached responses, and graceful degradation.
"""

from __future__ import annotations

import logging
import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Type, TypeVar
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

from .integ_constants import Priority
from .integ_exceptions import (
    IntegrationError, FallbackError, FallbackExecutionError, 
    FallbackNotAvailableError, IntegrationConnectionError,
    IntegrationTimeoutError
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class FallbackStrategy(Enum):
    """Fallback strategy types."""
    CACHED_RESPONSE = "cached_response"
    ALTERNATIVE_INTEGRATION = "alternative_integration"
    DEFAULT_RESPONSE = "default_response"
    SIMULATED_RESPONSE = "simulated_response"
    DEGRADED_SERVICE = "degraded_service"
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    CIRCUIT_BREAKER = "circuit_breaker"


class FallbackTrigger(Enum):
    """Fallback trigger conditions."""
    CONNECTION_ERROR = "connection_error"
    TIMEOUT_ERROR = "timeout_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    AUTHENTICATION_ERROR = "authentication_error"
    VALIDATION_ERROR = "validation_error"
    SERVER_ERROR = "server_error"
    CUSTOM_CONDITION = "custom_condition"


@dataclass
class FallbackCondition:
    """Fallback condition configuration."""
    trigger: FallbackTrigger
    error_types: List[Type[Exception]]
    custom_condition: Optional[Callable[[Exception], bool]] = None
    max_attempts: int = 3
    timeout_seconds: int = 30


@dataclass
class FallbackAction:
    """Fallback action configuration."""
    strategy: FallbackStrategy
    action_func: Callable
    priority: Priority = Priority.NORMAL
    timeout: int = 30
    retry_attempts: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FallbackRule:
    """Complete fallback rule configuration."""
    name: str
    integration_name: str
    conditions: List[FallbackCondition]
    actions: List[FallbackAction]
    enabled: bool = True
    created_at: datetime = field(default_factory=timezone.now)
    last_used: Optional[datetime] = None
    usage_count: int = 0
    success_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FallbackResult:
    """Fallback execution result."""
    rule_name: str
    strategy_used: FallbackStrategy
    success: bool
    result: Optional[Any] = None
    error: Optional[Exception] = None
    execution_time: float = 0.0
    attempts: int = 0
    timestamp: datetime = field(default_factory=timezone.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class FallbackProvider(ABC):
    """
    Abstract base class for fallback providers.
    """
    
    @abstractmethod
    async def execute_fallback(self, context: Dict[str, Any]) -> Any:
        """Execute fallback logic."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if fallback provider is available."""
        pass


class CachedResponseProvider(FallbackProvider):
    """Fallback provider that returns cached responses."""
    
    def __init__(self, cache_ttl: int = 3600):
        """Initialize cached response provider."""
        self.cache_ttl = cache_ttl
    
    async def execute_fallback(self, context: Dict[str, Any]) -> Any:
        """Execute cached response fallback."""
        cache_key = context.get('cache_key')
        if not cache_key:
            raise FallbackError("No cache key provided for cached response fallback")
        
        cached_response = cache.get(cache_key)
        if cached_response is None:
            raise FallbackNotAvailableError("No cached response available")
        
        return cached_response
    
    def is_available(self) -> bool:
        """Check if cached response provider is available."""
        return True


class AlternativeIntegrationProvider(FallbackProvider):
    """Fallback provider that uses alternative integrations."""
    
    def __init__(self, alternative_integrations: List[str]):
        """Initialize alternative integration provider."""
        self.alternative_integrations = alternative_integrations
    
    async def execute_fallback(self, context: Dict[str, Any]) -> Any:
        """Execute alternative integration fallback."""
        method = context.get('method')
        data = context.get('data', {})
        
        for integration_name in self.alternative_integrations:
            try:
                # Try alternative integration
                # This would integrate with the integration registry
                logger.info(f"Trying alternative integration: {integration_name}")
                
                # For now, return a mock response
                return {
                    'status': 'success',
                    'source': f'alternative_{integration_name}',
                    'data': data
                }
                
            except Exception as e:
                logger.warning(f"Alternative integration {integration_name} failed: {e}")
                continue
        
        raise FallbackNotAvailableError("All alternative integrations failed")
    
    def is_available(self) -> bool:
        """Check if alternative integration provider is available."""
        return len(self.alternative_integrations) > 0


class DefaultResponseProvider(FallbackProvider):
    """Fallback provider that returns default responses."""
    
    def __init__(self, default_responses: Dict[str, Any]):
        """Initialize default response provider."""
        self.default_responses = default_responses
    
    async def execute_fallback(self, context: Dict[str, Any]) -> Any:
        """Execute default response fallback."""
        method = context.get('method', 'default')
        
        if method in self.default_responses:
            return self.default_responses[method]
        
        # Return generic default response
        return {
            'status': 'degraded',
            'message': 'Service temporarily unavailable',
            'timestamp': timezone.now().isoformat()
        }
    
    def is_available(self) -> bool:
        """Check if default response provider is available."""
        return True


class SimulatedResponseProvider(FallbackProvider):
    """Fallback provider that returns simulated responses."""
    
    def __init__(self, response_templates: Dict[str, Any]):
        """Initialize simulated response provider."""
        self.response_templates = response_templates
    
    async def execute_fallback(self, context: Dict[str, Any]) -> Any:
        """Execute simulated response fallback."""
        method = context.get('method', 'default')
        data = context.get('data', {})
        
        if method in self.response_templates:
            template = self.response_templates[method]
            if callable(template):
                return template(data)
            else:
                return template
        
        # Generate generic simulated response
        return {
            'status': 'simulated',
            'method': method,
            'data': data,
            'timestamp': timezone.now().isoformat(),
            'message': 'This is a simulated response'
        }
    
    def is_available(self) -> bool:
        """Check if simulated response provider is available."""
        return True


class DegradedServiceProvider(FallbackProvider):
    """Fallback provider that provides degraded service functionality."""
    
    def __init__(self, degraded_functions: Dict[str, Callable]):
        """Initialize degraded service provider."""
        self.degraded_functions = degraded_functions
    
    async def execute_fallback(self, context: Dict[str, Any]) -> Any:
        """Execute degraded service fallback."""
        method = context.get('method')
        data = context.get('data', {})
        
        if method in self.degraded_functions:
            func = self.degraded_functions[method]
            if asyncio.iscoroutinefunction(func):
                return await func(data)
            else:
                return func(data)
        
        raise FallbackNotAvailableError(f"No degraded function available for {method}")
    
    def is_available(self) -> bool:
        """Check if degraded service provider is available."""
        return len(self.degraded_functions) > 0


class RetryWithBackoffProvider(FallbackProvider):
    """Fallback provider that implements retry with exponential backoff."""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
        """Initialize retry with backoff provider."""
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    async def execute_fallback(self, context: Dict[str, Any]) -> Any:
        """Execute retry with backoff fallback."""
        original_func = context.get('original_func')
        if not original_func:
            raise FallbackError("No original function provided for retry fallback")
        
        args = context.get('args', [])
        kwargs = context.get('kwargs', {})
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(original_func):
                    return await original_func(*args, **kwargs)
                else:
                    return original_func(*args, **kwargs)
                    
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    await asyncio.sleep(delay)
                    logger.info(f"Retry attempt {attempt + 1}/{self.max_retries} after {delay}s delay")
        
        raise FallbackExecutionError(f"All retry attempts failed: {last_exception}", 
                                     original_error=last_exception)
    
    def is_available(self) -> bool:
        """Check if retry with backoff provider is available."""
        return True


class FallbackHandler:
    """
    Main fallback handler for integration failures.
    
    Provides comprehensive fallback mechanisms including
    alternative methods, cached responses, and graceful degradation.
    """
    
    def __init__(self):
        """Initialize fallback handler."""
        self.rules: Dict[str, FallbackRule] = {}
        self.providers: Dict[FallbackStrategy, FallbackProvider] = {}
        
        # Statistics
        self.total_fallbacks = 0
        self.successful_fallbacks = 0
        self.failed_fallbacks = 0
        
        # Configuration
        self.enable_fallback_cache = getattr(settings, 'FALLBACK_ENABLE_CACHE', True)
        self.fallback_cache_ttl = getattr(settings, 'FALLBACK_CACHE_TTL', 3600)
        
        # Initialize default providers
        self._initialize_default_providers()
        
        logger.info("FallbackHandler initialized")
    
    def _initialize_default_providers(self) -> None:
        """Initialize default fallback providers."""
        self.providers[FallbackStrategy.CACHED_RESPONSE] = CachedResponseProvider()
        self.providers[FallbackStrategy.ALTERNATIVE_INTEGRATION] = AlternativeIntegrationProvider([])
        self.providers[FallbackStrategy.DEFAULT_RESPONSE] = DefaultResponseProvider({})
        self.providers[FallbackStrategy.SIMULATED_RESPONSE] = SimulatedResponseProvider({})
        self.providers[FallbackStrategy.DEGRADED_SERVICE] = DegradedServiceProvider({})
        self.providers[FallbackStrategy.RETRY_WITH_BACKOFF] = RetryWithBackoffProvider()
    
    def register_rule(self, rule: FallbackRule) -> None:
        """
        Register a fallback rule.
        
        Args:
            rule: Fallback rule to register
        """
        self.rules[rule.name] = rule
        logger.info(f"Registered fallback rule: {rule.name}")
    
    def unregister_rule(self, rule_name: str) -> bool:
        """
        Unregister a fallback rule.
        
        Args:
            rule_name: Name of rule to unregister
            
        Returns:
            True if rule was unregistered
        """
        if rule_name in self.rules:
            del self.rules[rule_name]
            logger.info(f"Unregistered fallback rule: {rule_name}")
            return True
        return False
    
    def register_provider(self, strategy: FallbackStrategy, provider: FallbackProvider) -> None:
        """
        Register a fallback provider.
        
        Args:
            strategy: Fallback strategy
            provider: Provider instance
        """
        self.providers[strategy] = provider
        logger.info(f"Registered fallback provider for {strategy.value}")
    
    async def handle_fallback(self, integration_name: str, method: str, 
                            original_exception: Exception, *args, **kwargs) -> Optional[FallbackResult]:
        """
        Handle fallback for integration failure.
        
        Args:
            integration_name: Name of integration that failed
            method: Method that was being called
            original_exception: Exception that caused the failure
            *args: Original method arguments
            **kwargs: Original method keyword arguments
            
        Returns:
            Fallback result or None if no fallback available
        """
        self.total_fallbacks += 1
        
        # Find applicable rules
        applicable_rules = self._find_applicable_rules(integration_name, original_exception)
        
        if not applicable_rules:
            logger.warning(f"No fallback rules found for {integration_name}: {original_exception}")
            self.failed_fallbacks += 1
            return None
        
        # Sort rules by priority
        applicable_rules.sort(key=lambda r: min(action.priority.value for action in r.actions))
        
        # Try each rule
        for rule in applicable_rules:
            try:
                result = await self._execute_fallback_rule(rule, method, original_exception, *args, **kwargs)
                
                if result.success:
                    self.successful_fallbacks += 1
                    rule.success_count += 1
                    logger.info(f"Fallback successful for {integration_name} using {result.strategy_used.value}")
                    return result
                else:
                    logger.warning(f"Fallback failed for {integration_name}: {result.error}")
                    
            except Exception as e:
                logger.error(f"Fallback execution error for {integration_name}: {e}")
                continue
        
        # All fallbacks failed
        self.failed_fallbacks += 1
        return None
    
    def _find_applicable_rules(self, integration_name: str, exception: Exception) -> List[FallbackRule]:
        """Find fallback rules applicable to the exception."""
        applicable_rules = []
        
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            
            if rule.integration_name != integration_name and rule.integration_name != '*':
                continue
            
            # Check if any condition matches
            for condition in rule.conditions:
                if self._condition_matches(condition, exception):
                    applicable_rules.append(rule)
                    break
        
        return applicable_rules
    
    def _condition_matches(self, condition: FallbackCondition, exception: Exception) -> bool:
        """Check if fallback condition matches the exception."""
        # Check error type
        for error_type in condition.error_types:
            if isinstance(exception, error_type):
                return True
        
        # Check custom condition
        if condition.custom_condition and condition.custom_condition(exception):
            return True
        
        return False
    
    async def _execute_fallback_rule(self, rule: FallbackRule, method: str, 
                                   original_exception: Exception, *args, **kwargs) -> FallbackResult:
        """Execute a fallback rule."""
        start_time = time.time()
        rule.last_used = timezone.now()
        rule.usage_count += 1
        
        # Try each action in order
        for action in rule.actions:
            try:
                provider = self.providers.get(action.strategy)
                if not provider or not provider.is_available():
                    continue
                
                # Prepare context for provider
                context = {
                    'integration_name': rule.integration_name,
                    'method': method,
                    'original_exception': original_exception,
                    'args': args,
                    'kwargs': kwargs,
                    'rule_name': rule.name,
                    'action_metadata': action.metadata
                }
                
                # Add cache key if available
                if hasattr(original_exception, '__dict__'):
                    context['cache_key'] = f"fallback_{rule.integration_name}_{method}"
                
                # Execute fallback
                result = await provider.execute_fallback(context)
                
                return FallbackResult(
                    rule_name=rule.name,
                    strategy_used=action.strategy,
                    success=True,
                    result=result,
                    execution_time=time.time() - start_time,
                    attempts=1,
                    metadata={'provider': type(provider).__name__}
                )
                
            except Exception as e:
                logger.warning(f"Fallback action {action.strategy.value} failed: {e}")
                continue
        
        # All actions failed
        return FallbackResult(
            rule_name=rule.name,
            strategy_used=rule.actions[0].strategy if rule.actions else FallbackStrategy.DEFAULT_RESPONSE,
            success=False,
            error=original_exception,
            execution_time=time.time() - start_time,
            attempts=len(rule.actions),
            metadata={'error': str(original_exception)}
        )
    
    @asynccontextmanager
    async def fallback_context(self, integration_name: str, method: str):
        """
        Context manager for automatic fallback handling.
        
        Args:
            integration_name: Integration name
            method: Method name
            
        Yields:
            Context for fallback handling
        """
        try:
            yield
        except Exception as e:
            fallback_result = await self.handle_fallback(integration_name, method, e)
            
            if fallback_result and fallback_result.success:
                self.last_fallback_result = fallback_result.result
                return
            else:
                raise
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get fallback statistics."""
        rule_stats = {}
        for rule_name, rule in self.rules.items():
            rule_stats[rule_name] = {
                'usage_count': rule.usage_count,
                'success_count': rule.success_count,
                'success_rate': (rule.success_count / max(rule.usage_count, 1)) * 100,
                'last_used': rule.last_used.isoformat() if rule.last_used else None,
                'enabled': rule.enabled
            }
        
        provider_stats = {}
        for strategy, provider in self.providers.items():
            provider_stats[strategy.value] = {
                'available': provider.is_available(),
                'type': type(provider).__name__
            }
        
        return {
            'total_fallbacks': self.total_fallbacks,
            'successful_fallbacks': self.successful_fallbacks,
            'failed_fallbacks': self.failed_fallbacks,
            'success_rate': (self.successful_fallbacks / max(self.total_fallbacks, 1)) * 100,
            'total_rules': len(self.rules),
            'enabled_rules': len([r for r in self.rules.values() if r.enabled]),
            'rule_statistics': rule_stats,
            'provider_statistics': provider_stats
        }
    
    def get_rule(self, rule_name: str) -> Optional[FallbackRule]:
        """Get fallback rule by name."""
        return self.rules.get(rule_name)
    
    def list_rules(self, integration_name: Optional[str] = None) -> List[FallbackRule]:
        """List fallback rules."""
        rules = list(self.rules.values())
        
        if integration_name:
            rules = [r for r in rules if r.integration_name == integration_name or r.integration_name == '*']
        
        return rules
    
    def enable_rule(self, rule_name: str) -> bool:
        """Enable a fallback rule."""
        rule = self.rules.get(rule_name)
        if rule:
            rule.enabled = True
            logger.info(f"Enabled fallback rule: {rule_name}")
            return True
        return False
    
    def disable_rule(self, rule_name: str) -> bool:
        """Disable a fallback rule."""
        rule = self.rules.get(rule_name)
        if rule:
            rule.enabled = False
            logger.info(f"Disabled fallback rule: {rule_name}")
            return True
        return False
    
    def cleanup(self) -> None:
        """Cleanup fallback handler resources."""
        self.rules.clear()
        self.providers.clear()
        
        # Reset statistics
        self.total_fallbacks = 0
        self.successful_fallbacks = 0
        self.failed_fallbacks = 0
        
        logger.info("FallbackHandler cleanup completed")


# Global fallback handler instance
_fallback_handler = None


def get_fallback_handler() -> FallbackHandler:
    """Get global fallback handler instance."""
    global _fallback_handler
    if _fallback_handler is None:
        _fallback_handler = FallbackHandler()
    return _fallback_handler


# Decorator for automatic fallback handling
def fallback_handler(integration_name: str, method: str = None):
    """
    Decorator for automatic fallback handling.
    
    Args:
        integration_name: Integration name
        method: Method name (optional, derived from function name if not provided)
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            handler = get_fallback_handler()
            method_name = method or func.__name__
            
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
                    
            except Exception as e:
                fallback_result = await handler.handle_fallback(
                    integration_name, method_name, e, *args, **kwargs
                )
                
                if fallback_result and fallback_result.success:
                    return fallback_result.result
                else:
                    raise
        
        return wrapper
    return decorator


# Convenience functions
async def execute_with_fallback(integration_name: str, method: str, func: Callable, 
                             *args, **kwargs) -> Any:
    """
    Execute function with automatic fallback handling.
    
    Args:
        integration_name: Integration name
        method: Method name
        func: Function to execute
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        Function result or fallback result
    """
    handler = get_fallback_handler()
    
    try:
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
            
    except Exception as e:
        fallback_result = await handler.handle_fallback(integration_name, method, e, *args, **kwargs)
        
        if fallback_result and fallback_result.success:
            return fallback_result.result
        else:
            raise


def register_fallback_rule(rule: FallbackRule) -> None:
    """
    Convenience function for registering fallback rule.
    
    Args:
        rule: Fallback rule to register
    """
    handler = get_fallback_handler()
    handler.register_rule(rule)


def get_fallback_statistics() -> Dict[str, Any]:
    """
    Convenience function for getting fallback statistics.
    
    Returns:
        Fallback statistics
    """
    handler = get_fallback_handler()
    return handler.get_statistics()
