"""
Integration Handler
Main handler for managing integration operations and orchestrating different components
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from .integ_registry import IntegrationRegistry
from .event_bus import EventBus
from .data_validator import DataValidator
from .circuit_breaker import CircuitBreaker
from .performance_monitor import PerformanceMonitor
from .integ_exceptions import IntegrationException, HandlerException
from .integ_constants import IntegrationStatus, EventTypes, HandlerConfig
from .fallback_logic import FallbackLogic

logger = logging.getLogger(__name__)


class HandlerMode(Enum):
    """Handler operation modes"""
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    BATCH = "batch"
    STREAMING = "streaming"


@dataclass
class IntegrationRequest:
    """Integration request data structure"""
    request_id: str
    source_system: str
    target_system: str
    event_type: str
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
    priority: int = 5
    timeout: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class IntegrationResponse:
    """Integration response data structure"""
    request_id: str
    status: IntegrationStatus
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    processing_time: Optional[float] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class IntegrationHandler:
    """
    Main integration handler that orchestrates all integration operations
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or HandlerConfig.DEFAULT_CONFIG
        self.registry = IntegrationRegistry()
        self.event_bus = EventBus()
        self.data_validator = DataValidator()
        self.performance_monitor = PerformanceMonitor()
        self.fallback_logic = FallbackLogic()
        
        # Circuit breakers for different systems
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Handler state
        self.mode = HandlerMode.SYNCHRONOUS
        self.is_running = False
        self.request_queue: List[IntegrationRequest] = []
        self.active_requests: Dict[str, IntegrationRequest] = {}
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'average_processing_time': 0.0
        }
        
        # Initialize circuit breakers
        self._initialize_circuit_breakers()
    
    def start(self):
        """Start the integration handler"""
        if self.is_running:
            logger.warning("Integration handler is already running")
            return
        
        try:
            self.is_running = True
            self.event_bus.start()
            self.performance_monitor.start()
            
            logger.info("Integration handler started successfully")
            
        except Exception as e:
            self.is_running = False
            raise HandlerException(f"Failed to start integration handler: {e}")
    
    def stop(self):
        """Stop the integration handler"""
        if not self.is_running:
            return
        
        try:
            self.is_running = False
            self.event_bus.stop()
            self.performance_monitor.stop()
            
            # Wait for active requests to complete
            if self.active_requests:
                logger.warning(f"Waiting for {len(self.active_requests)} active requests to complete")
                # In a real implementation, you'd wait for requests to complete
            
            logger.info("Integration handler stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping integration handler: {e}")
    
    def set_mode(self, mode: HandlerMode):
        """Set the handler operation mode"""
        self.mode = mode
        logger.info(f"Integration handler mode set to: {mode.value}")
    
    async def process_request(self, request: IntegrationRequest) -> IntegrationResponse:
        """
        Process an integration request
        
        Args:
            request: Integration request to process
            
        Returns:
            Integration response
        """
        if not self.is_running:
            raise HandlerException("Integration handler is not running")
        
        start_time = datetime.utcnow()
        
        try:
            # Validate request
            self._validate_request(request)
            
            # Add to active requests
            self.active_requests[request.request_id] = request
            
            # Update statistics
            self.stats['total_requests'] += 1
            
            # Get circuit breaker for target system
            circuit_breaker = self._get_circuit_breaker(request.target_system)
            
            # Process through circuit breaker
            response = await circuit_breaker.call_async(
                self._process_request_internal,
                request
            )
            
            # Update processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            response.processing_time = processing_time
            
            # Update statistics
            if response.status == IntegrationStatus.SUCCESS:
                self.stats['successful_requests'] += 1
            else:
                self.stats['failed_requests'] += 1
            
            self._update_average_processing_time(processing_time)
            
            # Log performance
            self.performance_monitor.record_request(
                request.source_system,
                request.target_system,
                processing_time,
                response.status
            )
            
            return response
            
        except Exception as e:
            # Create error response
            response = IntegrationResponse(
                request_id=request.request_id,
                status=IntegrationStatus.FAILED,
                error=str(e),
                processing_time=(datetime.utcnow() - start_time).total_seconds()
            )
            
            self.stats['failed_requests'] += 1
            
            # Try fallback logic
            fallback_response = await self.fallback_logic.handle_failure(request, e)
            if fallback_response:
                response = fallback_response
            
            return response
            
        finally:
            # Remove from active requests
            self.active_requests.pop(request.request_id, None)
    
    async def process_request_internal(self, request: IntegrationRequest) -> IntegrationResponse:
        """
        Internal request processing logic
        """
        try:
            # Get adapter for source and target systems
            source_adapter = self.registry.get_adapter(request.source_system)
            target_adapter = self.registry.get_adapter(request.target_system)
            
            if not source_adapter or not target_adapter:
                raise IntegrationException(f"Adapter not found for {request.source_system} or {request.target_system}")
            
            # Transform data if needed
            transformed_data = await self._transform_data(
                request.data,
                source_adapter,
                target_adapter
            )
            
            # Validate transformed data
            validation_result = self.data_validator.validate(
                transformed_data,
                request.target_system
            )
            
            if not validation_result.is_valid:
                raise IntegrationException(f"Data validation failed: {validation_result.errors}")
            
            # Execute integration
            result = await self._execute_integration(
                request,
                source_adapter,
                target_adapter,
                transformed_data
            )
            
            # Create success response
            response = IntegrationResponse(
                request_id=request.request_id,
                status=IntegrationStatus.SUCCESS,
                data=result,
                metadata={
                    'source_system': request.source_system,
                    'target_system': request.target_system,
                    'event_type': request.event_type,
                    'validation_result': validation_result.to_dict()
                }
            )
            
            # Publish event
            await self.event_bus.publish(
                EventTypes.INTEGRATION_COMPLETED,
                {
                    'request_id': request.request_id,
                    'source_system': request.source_system,
                    'target_system': request.target_system,
                    'status': 'success'
                }
            )
            
            return response
            
        except Exception as e:
            # Create error response
            response = IntegrationResponse(
                request_id=request.request_id,
                status=IntegrationStatus.FAILED,
                error=str(e)
            )
            
            # Publish error event
            await self.event_bus.publish(
                EventTypes.INTEGRATION_FAILED,
                {
                    'request_id': request.request_id,
                    'source_system': request.source_system,
                    'target_system': request.target_system,
                    'error': str(e)
                }
            )
            
            return response
    
    async def process_batch(self, requests: List[IntegrationRequest]) -> List[IntegrationResponse]:
        """
        Process multiple integration requests in batch
        
        Args:
            requests: List of integration requests
            
        Returns:
            List of integration responses
        """
        if self.mode != HandlerMode.BATCH:
            raise HandlerException("Handler not in batch mode")
        
        responses = []
        
        # Process requests concurrently
        tasks = [self.process_request(request) for request in requests]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error responses
        final_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                final_responses.append(IntegrationResponse(
                    request_id=requests[i].request_id,
                    status=IntegrationStatus.FAILED,
                    error=str(response)
                ))
            else:
                final_responses.append(response)
        
        return final_responses
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get handler status and statistics
        
        Returns:
            Handler status information
        """
        return {
            'is_running': self.is_running,
            'mode': self.mode.value,
            'active_requests': len(self.active_requests),
            'queued_requests': len(self.request_queue),
            'statistics': self.stats.copy(),
            'circuit_breakers': {
                name: cb.get_state()
                for name, cb in self.circuit_breakers.items()
            },
            'performance_metrics': self.performance_monitor.get_metrics()
        }
    
    def _validate_request(self, request: IntegrationRequest):
        """Validate integration request"""
        if not request.request_id:
            raise IntegrationException("Request ID is required")
        
        if not request.source_system or not request.target_system:
            raise IntegrationException("Source and target systems are required")
        
        if not request.event_type:
            raise IntegrationException("Event type is required")
        
        if not request.data:
            raise IntegrationException("Request data is required")
        
        if request.retry_count > request.max_retries:
            raise IntegrationException("Maximum retry count exceeded")
    
    async def _transform_data(self, data: Dict[str, Any], source_adapter, target_adapter) -> Dict[str, Any]:
        """Transform data from source to target format"""
        from .transformer import DataTransformer
        
        transformer = DataTransformer()
        
        # Get transformation rules
        transformation_rules = await self.registry.get_transformation_rules(
            source_adapter.system_name,
            target_adapter.system_name
        )
        
        if transformation_rules:
            return transformer.transform(data, transformation_rules)
        else:
            # No transformation needed
            return data
    
    async def _execute_integration(self, request: IntegrationRequest, source_adapter, target_adapter, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the integration operation"""
        # This would depend on the specific integration type
        # For now, return the transformed data as result
        return {
            'processed_data': data,
            'integration_type': f"{request.source_system}_to_{request.target_system}",
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _initialize_circuit_breakers(self):
        """Initialize circuit breakers for all registered systems"""
        systems = self.registry.get_registered_systems()
        
        for system in systems:
            self.circuit_breakers[system] = CircuitBreaker(
                name=system,
                failure_threshold=self.config.get('circuit_breaker_failure_threshold', 5),
                recovery_timeout=self.config.get('circuit_breaker_recovery_timeout', 60),
                expected_exception=IntegrationException
            )
    
    def _get_circuit_breaker(self, system: str) -> CircuitBreaker:
        """Get circuit breaker for a system"""
        if system not in self.circuit_breakers:
            # Create new circuit breaker for unknown system
            self.circuit_breakers[system] = CircuitBreaker(
                name=system,
                failure_threshold=self.config.get('circuit_breaker_failure_threshold', 5),
                recovery_timeout=self.config.get('circuit_breaker_recovery_timeout', 60)
            )
        
        return self.circuit_breakers[system]
    
    def _update_average_processing_time(self, processing_time: float):
        """Update average processing time"""
        total_requests = self.stats['total_requests']
        current_avg = self.stats['average_processing_time']
        
        # Calculate new average
        new_avg = ((current_avg * (total_requests - 1)) + processing_time) / total_requests
        self.stats['average_processing_time'] = new_avg


# Global handler instance
_integration_handler = None


def get_integration_handler() -> IntegrationHandler:
    """Get the global integration handler instance"""
    global _integration_handler
    if _integration_handler is None:
        _integration_handler = IntegrationHandler()
    return _integration_handler


def initialize_integration_handler(config: Optional[Dict[str, Any]] = None):
    """Initialize the global integration handler"""
    global _integration_handler
    _integration_handler = IntegrationHandler(config)
    return _integration_handler


# Export main classes and functions
__all__ = [
    'IntegrationHandler',
    'IntegrationRequest',
    'IntegrationResponse',
    'HandlerMode',
    'get_integration_handler',
    'initialize_integration_handler',
]
