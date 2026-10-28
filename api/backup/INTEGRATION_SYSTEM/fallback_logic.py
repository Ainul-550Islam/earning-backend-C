"""
Fallback Logic
Comprehensive fallback mechanisms for integration failures
"""

import logging
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
from abc import ABC, abstractmethod

from .integ_exceptions import IntegrationException, FallbackException
from .integ_adapter import BaseIntegrationAdapter

logger = logging.getLogger(__name__)


class FallbackStrategy(Enum):
    """Fallback strategy types"""
    RETRY = "retry"
    CIRCUIT_BREAKER = "circuit_breaker"
    ALTERNATIVE_SYSTEM = "alternative_system"
    CACHE_FALLBACK = "cache_fallback"
    DEFAULT_RESPONSE = "default_response"
    DEGRADED_SERVICE = "degraded_service"
    MANUAL_INTERVENTION = "manual_intervention"
    FAIL_FAST = "fail_fast"


class FallbackTrigger(Enum):
    """Fallback trigger conditions"""
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    AUTHENTICATION_ERROR = "authentication_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    SERVER_ERROR = "server_error"
    NETWORK_ERROR = "network_error"
    VALIDATION_ERROR = "validation_error"
    CUSTOM_CONDITION = "custom_condition"


@dataclass
class FallbackRule:
    """Fallback rule definition"""
    rule_id: str
    strategy: FallbackStrategy
    trigger_conditions: List[FallbackTrigger]
    max_attempts: int = 3
    retry_delay: float = 1.0
    backoff_multiplier: float = 2.0
    timeout: Optional[float] = None
    alternative_systems: List[str] = field(default_factory=list)
    cache_ttl: Optional[int] = None
    default_response: Optional[Dict[str, Any]] = None
    enabled: bool = True
    priority: int = 5
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FallbackContext:
    """Context for fallback execution"""
    operation_id: str
    system: str
    operation: str
    original_request: Dict[str, Any]
    attempt_count: int = 0
    start_time: datetime = field(default_factory=datetime.utcnow)
    last_attempt_time: Optional[datetime] = None
    errors: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FallbackResult:
    """Result of fallback execution"""
    success: bool
    strategy_used: Optional[FallbackStrategy] = None
    response: Optional[Dict[str, Any]] = None
    error: Optional[Exception] = None
    attempt_count: int = 0
    total_time: float = 0.0
    fallback_used: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseFallbackHandler(ABC):
    """Abstract base class for fallback handlers"""
    
    @abstractmethod
    async def handle_fallback(self, context: FallbackContext, rule: FallbackRule) -> FallbackResult:
        """Handle fallback execution"""
        pass
    
    @abstractmethod
    def can_handle(self, strategy: FallbackStrategy) -> bool:
        """Check if handler can handle the strategy"""
        pass


class RetryHandler(BaseFallbackHandler):
    """Handler for retry fallback strategy"""
    
    def can_handle(self, strategy: FallbackStrategy) -> bool:
        return strategy == FallbackStrategy.RETRY
    
    async def handle_fallback(self, context: FallbackContext, rule: FallbackRule) -> FallbackResult:
        """Handle retry fallback"""
        start_time = datetime.utcnow()
        
        try:
            # Calculate delay with exponential backoff
            delay = rule.retry_delay * (rule.backoff_multiplier ** (context.attempt_count - 1))
            
            # Wait before retry
            await asyncio.sleep(delay)
            
            # Execute the original operation
            result = await self._execute_operation(context)
            
            return FallbackResult(
                success=True,
                strategy_used=FallbackStrategy.RETRY,
                response=result,
                attempt_count=context.attempt_count,
                total_time=(datetime.utcnow() - start_time).total_seconds(),
                fallback_used=True,
                metadata={'retry_delay': delay}
            )
            
        except Exception as e:
            return FallbackResult(
                success=False,
                strategy_used=FallbackStrategy.RETRY,
                error=e,
                attempt_count=context.attempt_count,
                total_time=(datetime.utcnow() - start_time).total_seconds(),
                fallback_used=True,
                metadata={'retry_delay': delay}
            )
    
    async def _execute_operation(self, context: FallbackContext) -> Dict[str, Any]:
        """Execute the original operation"""
        # This would be implemented based on the specific operation
        # For now, return a mock response
        return {'status': 'success', 'data': 'retry_success'}


class CircuitBreakerHandler(BaseFallbackHandler):
    """Handler for circuit breaker fallback strategy"""
    
    def __init__(self):
        self.circuit_states: Dict[str, Dict[str, Any]] = {}
    
    def can_handle(self, strategy: FallbackStrategy) -> bool:
        return strategy == FallbackStrategy.CIRCUIT_BREAKER
    
    async def handle_fallback(self, context: FallbackContext, rule: FallbackRule) -> FallbackResult:
        """Handle circuit breaker fallback"""
        start_time = datetime.utcnow()
        
        circuit_key = f"{context.system}:{context.operation}"
        circuit_state = self._get_circuit_state(circuit_key)
        
        if circuit_state['state'] == 'open':
            # Circuit is open, return fallback response
            return FallbackResult(
                success=True,
                strategy_used=FallbackStrategy.CIRCUIT_BREAKER,
                response=self._get_fallback_response(context),
                attempt_count=context.attempt_count,
                total_time=(datetime.utcnow() - start_time).total_seconds(),
                fallback_used=True,
                metadata={'circuit_state': 'open', 'opens_at': circuit_state['opens_at']}
            )
        
        # Try to execute operation
        try:
            result = await self._execute_operation(context)
            
            # Success, reset circuit if needed
            if circuit_state['state'] == 'half_open':
                self._reset_circuit(circuit_key)
            
            return FallbackResult(
                success=True,
                strategy_used=FallbackStrategy.CIRCUIT_BREAKER,
                response=result,
                attempt_count=context.attempt_count,
                total_time=(datetime.utcnow() - start_time).total_seconds(),
                fallback_used=False,
                metadata={'circuit_state': circuit_state['state']}
            )
            
        except Exception as e:
            # Failure, update circuit state
            self._update_circuit_state(circuit_key, rule)
            
            return FallbackResult(
                success=False,
                strategy_used=FallbackStrategy.CIRCUIT_BREAKER,
                error=e,
                attempt_count=context.attempt_count,
                total_time=(datetime.utcnow() - start_time).total_seconds(),
                fallback_used=True,
                metadata={'circuit_state': circuit_state['state']}
            )
    
    def _get_circuit_state(self, circuit_key: str) -> Dict[str, Any]:
        """Get circuit state"""
        if circuit_key not in self.circuit_states:
            self.circuit_states[circuit_key] = {
                'state': 'closed',
                'failure_count': 0,
                'last_failure_time': None,
                'opens_at': None
            }
        return self.circuit_states[circuit_key]
    
    def _update_circuit_state(self, circuit_key: str, rule: FallbackRule):
        """Update circuit state after failure"""
        circuit_state = self.circuit_states[circuit_key]
        circuit_state['failure_count'] += 1
        circuit_state['last_failure_time'] = datetime.utcnow()
        
        # Open circuit if threshold reached
        if circuit_state['failure_count'] >= rule.max_attempts:
            circuit_state['state'] = 'open'
            circuit_state['opens_at'] = datetime.utcnow() + timedelta(seconds=rule.retry_delay)
    
    def _reset_circuit(self, circuit_key: str):
        """Reset circuit to closed state"""
        self.circuit_states[circuit_key] = {
            'state': 'closed',
            'failure_count': 0,
            'last_failure_time': None,
            'opens_at': None
        }
    
    def _get_fallback_response(self, context: FallbackContext) -> Dict[str, Any]:
        """Get fallback response when circuit is open"""
        return {
            'status': 'circuit_breaker_open',
            'message': 'Service temporarily unavailable',
            'retry_after': 60
        }
    
    async def _execute_operation(self, context: FallbackContext) -> Dict[str, Any]:
        """Execute the original operation"""
        # This would be implemented based on the specific operation
        return {'status': 'success', 'data': 'circuit_breaker_success'}


class AlternativeSystemHandler(BaseFallbackHandler):
    """Handler for alternative system fallback strategy"""
    
    def __init__(self):
        self.system_adapters: Dict[str, BaseIntegrationAdapter] = {}
    
    def can_handle(self, strategy: FallbackStrategy) -> bool:
        return strategy == FallbackStrategy.ALTERNATIVE_SYSTEM
    
    async def handle_fallback(self, context: FallbackContext, rule: FallbackRule) -> FallbackResult:
        """Handle alternative system fallback"""
        start_time = datetime.utcnow()
        
        for alternative_system in rule.alternative_systems:
            try:
                adapter = self.system_adapters.get(alternative_system)
                if not adapter:
                    continue
                
                # Try alternative system
                result = await adapter.send_data(context.original_request)
                
                return FallbackResult(
                    success=True,
                    strategy_used=FallbackStrategy.ALTERNATIVE_SYSTEM,
                    response=result,
                    attempt_count=context.attempt_count,
                    total_time=(datetime.utcnow() - start_time).total_seconds(),
                    fallback_used=True,
                    metadata={'alternative_system': alternative_system}
                )
                
            except Exception as e:
                logger.warning(f"Alternative system {alternative_system} failed: {e}")
                continue
        
        # All alternatives failed
        return FallbackResult(
            success=False,
            strategy_used=FallbackStrategy.ALTERNATIVE_SYSTEM,
            error=Exception("All alternative systems failed"),
            attempt_count=context.attempt_count,
            total_time=(datetime.utcnow() - start_time).total_seconds(),
            fallback_used=True,
            metadata={'attempted_systems': rule.alternative_systems}
        )
    
    def register_adapter(self, system_name: str, adapter: BaseIntegrationAdapter):
        """Register an adapter for a system"""
        self.system_adapters[system_name] = adapter


class CacheFallbackHandler(BaseFallbackHandler):
    """Handler for cache fallback strategy"""
    
    def __init__(self):
        self.cache: Dict[str, Dict[str, Any]] = {}
    
    def can_handle(self, strategy: FallbackStrategy) -> bool:
        return strategy == FallbackStrategy.CACHE_FALLBACK
    
    async def handle_fallback(self, context: FallbackContext, rule: FallbackRule) -> FallbackResult:
        """Handle cache fallback"""
        start_time = datetime.utcnow()
        
        cache_key = self._generate_cache_key(context)
        cached_data = self.cache.get(cache_key)
        
        if cached_data and self._is_cache_valid(cached_data, rule):
            return FallbackResult(
                success=True,
                strategy_used=FallbackStrategy.CACHE_FALLBACK,
                response=cached_data['data'],
                attempt_count=context.attempt_count,
                total_time=(datetime.utcnow() - start_time).total_seconds(),
                fallback_used=True,
                metadata={'cache_hit': True, 'cache_age': (datetime.utcnow() - cached_data['timestamp']).total_seconds()}
            )
        
        return FallbackResult(
            success=False,
            strategy_used=FallbackStrategy.CACHE_FALLBACK,
            error=Exception("No valid cache data available"),
            attempt_count=context.attempt_count,
            total_time=(datetime.utcnow() - start_time).total_seconds(),
            fallback_used=True,
            metadata={'cache_hit': False}
        )
    
    def _generate_cache_key(self, context: FallbackContext) -> str:
        """Generate cache key for context"""
        import hashlib
        import json
        
        key_data = {
            'system': context.system,
            'operation': context.operation,
            'request': context.original_request
        }
        
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _is_cache_valid(self, cached_data: Dict[str, Any], rule: FallbackRule) -> bool:
        """Check if cache data is still valid"""
        if not rule.cache_ttl:
            return True
        
        age = (datetime.utcnow() - cached_data['timestamp']).total_seconds()
        return age < rule.cache_ttl
    
    def store_cache(self, context: FallbackContext, data: Dict[str, Any], ttl: Optional[int] = None):
        """Store data in cache"""
        cache_key = self._generate_cache_key(context)
        self.cache[cache_key] = {
            'data': data,
            'timestamp': datetime.utcnow(),
            'ttl': ttl
        }


class DefaultResponseHandler(BaseFallbackHandler):
    """Handler for default response fallback strategy"""
    
    def can_handle(self, strategy: FallbackStrategy) -> bool:
        return strategy == FallbackStrategy.DEFAULT_RESPONSE
    
    async def handle_fallback(self, context: FallbackContext, rule: FallbackRule) -> FallbackResult:
        """Handle default response fallback"""
        start_time = datetime.utcnow()
        
        default_response = rule.default_response or {
            'status': 'default',
            'message': 'Service unavailable, using default response'
        }
        
        return FallbackResult(
            success=True,
            strategy_used=FallbackStrategy.DEFAULT_RESPONSE,
            response=default_response,
            attempt_count=context.attempt_count,
            total_time=(datetime.utcnow() - start_time).total_seconds(),
            fallback_used=True,
            metadata={'default_response': True}
        )


class DegradedServiceHandler(BaseFallbackHandler):
    """Handler for degraded service fallback strategy"""
    
    def can_handle(self, strategy: FallbackStrategy) -> bool:
        return strategy == FallbackStrategy.DEGRADED_SERVICE
    
    async def handle_fallback(self, context: FallbackContext, rule: FallbackRule) -> FallbackResult:
        """Handle degraded service fallback"""
        start_time = datetime.utcnow()
        
        # Implement degraded service logic
        degraded_response = {
            'status': 'degraded',
            'message': 'Service running in degraded mode',
            'limited_functionality': True
        }
        
        return FallbackResult(
            success=True,
            strategy_used=FallbackStrategy.DEGRADED_SERVICE,
            response=degraded_response,
            attempt_count=context.attempt_count,
            total_time=(datetime.utcnow() - start_time).total_seconds(),
            fallback_used=True,
            metadata={'degraded_mode': True}
        )


class FallbackManager:
    """
    Manager for fallback logic and strategies
    """
    
    def __init__(self):
        self.fallback_rules: Dict[str, List[FallbackRule]] = {}
        self.handlers: Dict[FallbackStrategy, BaseFallbackHandler] = {}
        self.fallback_stats = {
            'total_fallbacks': 0,
            'successful_fallbacks': 0,
            'failed_fallbacks': 0,
            'fallbacks_by_strategy': {},
            'fallbacks_by_system': {}
        }
        
        # Initialize default handlers
        self._initialize_handlers()
    
    def _initialize_handlers(self):
        """Initialize default fallback handlers"""
        self.handlers[FallbackStrategy.RETRY] = RetryHandler()
        self.handlers[FallbackStrategy.CIRCUIT_BREAKER] = CircuitBreakerHandler()
        self.handlers[FallbackStrategy.ALTERNATIVE_SYSTEM] = AlternativeSystemHandler()
        self.handlers[FallbackStrategy.CACHE_FALLBACK] = CacheFallbackHandler()
        self.handlers[FallbackStrategy.DEFAULT_RESPONSE] = DefaultResponseHandler()
        self.handlers[FallbackStrategy.DEGRADED_SERVICE] = DegradedServiceHandler()
    
    def register_fallback_rule(self, system: str, operation: str, rule: FallbackRule):
        """Register a fallback rule for a system and operation"""
        key = f"{system}:{operation}"
        if key not in self.fallback_rules:
            self.fallback_rules[key] = []
        
        self.fallback_rules[key].append(rule)
        # Sort by priority
        self.fallback_rules[key].sort(key=lambda r: r.priority)
    
    def register_handler(self, strategy: FallbackStrategy, handler: BaseFallbackHandler):
        """Register a custom fallback handler"""
        self.handlers[strategy] = handler
    
    async def execute_with_fallback(self, system: str, operation: str, 
                                   request: Dict[str, Any],
                                   primary_operation: Optional[Callable] = None) -> FallbackResult:
        """
        Execute operation with fallback support
        
        Args:
            system: System name
            operation: Operation name
            request: Request data
            primary_operation: Primary operation to execute
            
        Returns:
            Fallback result
        """
        import uuid
        
        context = FallbackContext(
            operation_id=str(uuid.uuid4()),
            system=system,
            operation=operation,
            original_request=request
        )
        
        # Get fallback rules
        key = f"{system}:{operation}"
        rules = self.fallback_rules.get(key, [])
        
        # Try primary operation first
        if primary_operation:
            try:
                result = await primary_operation(request)
                return FallbackResult(
                    success=True,
                    response=result,
                    attempt_count=1,
                    total_time=0.0,
                    fallback_used=False
                )
            except Exception as e:
                context.errors.append({
                    'attempt': 1,
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                })
                context.attempt_count = 1
        
        # Execute fallback strategies
        for rule in rules:
            if not rule.enabled:
                continue
            
            # Check if trigger conditions match
            if not self._should_trigger_fallback(context, rule):
                continue
            
            # Get handler for strategy
            handler = self.handlers.get(rule.strategy)
            if not handler:
                logger.warning(f"No handler found for strategy: {rule.strategy}")
                continue
            
            try:
                # Execute fallback
                result = await handler.handle_fallback(context, rule)
                
                # Update statistics
                self._update_fallback_stats(rule.strategy, system, result.success)
                
                if result.success:
                    return result
                else:
                    context.errors.append({
                        'attempt': context.attempt_count + 1,
                        'strategy': rule.strategy.value,
                        'error': str(result.error) if result.error else 'Unknown error',
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    context.attempt_count += 1
                
            except Exception as e:
                logger.error(f"Fallback handler error: {e}")
                continue
        
        # All fallbacks failed
        return FallbackResult(
            success=False,
            error=Exception("All fallback strategies failed"),
            attempt_count=context.attempt_count,
            total_time=(datetime.utcnow() - context.start_time).total_seconds(),
            fallback_used=True
        )
    
    def _should_trigger_fallback(self, context: FallbackContext, rule: FallbackRule) -> bool:
        """Check if fallback should be triggered"""
        if not context.errors:
            return False
        
        # Check if any trigger conditions match
        for error in context.errors:
            error_message = error.get('error', '').lower()
            
            for trigger in rule.trigger_conditions:
                if trigger == FallbackTrigger.TIMEOUT and 'timeout' in error_message:
                    return True
                elif trigger == FallbackTrigger.CONNECTION_ERROR and 'connection' in error_message:
                    return True
                elif trigger == FallbackTrigger.AUTHENTICATION_ERROR and 'auth' in error_message:
                    return True
                elif trigger == FallbackTrigger.RATE_LIMIT_ERROR and 'rate limit' in error_message:
                    return True
                elif trigger == FallbackTrigger.SERVER_ERROR and 'server error' in error_message:
                    return True
                elif trigger == FallbackTrigger.NETWORK_ERROR and 'network' in error_message:
                    return True
                elif trigger == FallbackTrigger.VALIDATION_ERROR and 'validation' in error_message:
                    return True
        
        return False
    
    def _update_fallback_stats(self, strategy: FallbackStrategy, system: str, success: bool):
        """Update fallback statistics"""
        self.fallback_stats['total_fallbacks'] += 1
        
        if success:
            self.fallback_stats['successful_fallbacks'] += 1
        else:
            self.fallback_stats['failed_fallbacks'] += 1
        
        # Update by strategy
        strategy_name = strategy.value
        self.fallback_stats['fallbacks_by_strategy'][strategy_name] = (
            self.fallback_stats['fallbacks_by_strategy'].get(strategy_name, 0) + 1
        )
        
        # Update by system
        self.fallback_stats['fallbacks_by_system'][system] = (
            self.fallback_stats['fallbacks_by_system'].get(system, 0) + 1
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get fallback statistics"""
        stats = self.fallback_stats.copy()
        
        # Calculate success rate
        if stats['total_fallbacks'] > 0:
            stats['success_rate'] = (stats['successful_fallbacks'] / stats['total_fallbacks']) * 100
        else:
            stats['success_rate'] = 0
        
        return stats
    
    def get_fallback_rules(self, system: Optional[str] = None, 
                          operation: Optional[str] = None) -> List[FallbackRule]:
        """Get fallback rules with optional filtering"""
        rules = []
        
        for key, rule_list in self.fallback_rules.items():
            key_system, key_operation = key.split(':', 1)
            
            if system and key_system != system:
                continue
            
            if operation and key_operation != operation:
                continue
            
            rules.extend(rule_list)
        
        return rules


# Global fallback manager instance
_fallback_manager = None


def get_fallback_manager() -> FallbackManager:
    """Get the global fallback manager instance"""
    global _fallback_manager
    if _fallback_manager is None:
        _fallback_manager = FallbackManager()
    return _fallback_manager


def initialize_fallback_manager() -> FallbackManager:
    """Initialize the global fallback manager"""
    global _fallback_manager
    _fallback_manager = FallbackManager()
    return _fallback_manager


# Export main classes and functions
__all__ = [
    'FallbackManager',
    'FallbackRule',
    'FallbackContext',
    'FallbackResult',
    'BaseFallbackHandler',
    'RetryHandler',
    'CircuitBreakerHandler',
    'AlternativeSystemHandler',
    'CacheFallbackHandler',
    'DefaultResponseHandler',
    'DegradedServiceHandler',
    'FallbackStrategy',
    'FallbackTrigger',
    'get_fallback_manager',
    'initialize_fallback_manager',
]
