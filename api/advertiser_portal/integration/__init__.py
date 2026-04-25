"""
Integration Module for Advertiser Portal

This module provides comprehensive integration layers for connecting
the advertiser_portal with external modules and legacy systems.
"""

# Import main integration classes
from .data_bridge import DataBridge, DataSyncResult, data_bridge
from .performance_monitor import PerformanceMonitor, PerformanceMetric, performance_monitor, monitor_performance
from .event_bus import EventBus, Event, EventHandler, EventPriority, event_bus, event_handler
from .a_b_testing_integration import ABTestingIntegration, ABTestConfig, ABTestResult, ab_testing_integration
from .bidding_optimization_integration import BiddingOptimizationIntegration, BidRequest, BidResponse, OptimizationConfig, bidding_optimization_integration
from .retargeting_engines_integration import RetargetingEnginesIntegration, RetargetingSegment, UserJourneyEvent, RetargetingConfig, retargeting_engines_integration
from .webhooks_integration import WebhooksIntegration, WebhookConfig, WebhookDelivery, WebhookEvent, webhooks_integration

# Initialize all integration services
async def initialize_integrations():
    """Initialize all integration services."""
    # Start event bus processing
    await event_bus.start_processing()
    
    # Initialize integration services
    await ab_testing_integration._initialize_models()
    await bidding_optimization_integration._initialize_models()
    
    # Start background tasks
    try:
        _loop = asyncio.get_running_loop()
        _loop.create_task(retargeting_engines_integration._segment_refresh_loop())
    except RuntimeError:
        pass  # No running event loop at import time
    try:
        _loop = asyncio.get_running_loop()
        _loop.create_task(retargeting_engines_integration._performance_monitoring_loop())
    except RuntimeError:
        pass  # No running event loop at import time
    try:
        _loop = asyncio.get_running_loop()
        _loop.create_task(webhooks_integration._delivery_processing_loop())
    except RuntimeError:
        pass  # No running event loop at import time
    try:
        _loop = asyncio.get_running_loop()
        _loop.create_task(webhooks_integration._retry_processing_loop())
    except RuntimeError:
        pass  # No running event loop at import time
    try:
        _loop = asyncio.get_running_loop()
        _loop.create_task(webhooks_integration._cleanup_loop())
    except RuntimeError:
        pass  # No running event loop at import time


async def shutdown_integrations():
    """Shutdown all integration services."""
    # Stop event bus processing
    await event_bus.stop_processing()
    
    # Cleanup integration services
    webhooks_integration.executor.shutdown(wait=True)


# Export all integration classes
__all__ = [
    # Data Bridge
    'DataBridge',
    'DataSyncResult', 
    'data_bridge',
    
    # Performance Monitor
    'PerformanceMonitor',
    'PerformanceMetric',
    'performance_monitor',
    'monitor_performance',
    
    # Event Bus
    'EventBus',
    'Event',
    'EventHandler',
    'EventPriority',
    'event_bus',
    'event_handler',
    
    # A/B Testing Integration
    'ABTestingIntegration',
    'ABTestConfig',
    'ABTestResult',
    'ab_testing_integration',
    
    # Bidding Optimization Integration
    'BiddingOptimizationIntegration',
    'BidRequest',
    'BidResponse',
    'OptimizationConfig',
    'bidding_optimization_integration',
    
    # Retargeting Engines Integration
    'RetargetingEnginesIntegration',
    'RetargetingSegment',
    'UserJourneyEvent',
    'RetargetingConfig',
    'retargeting_engines_integration',
    
    # Webhooks Integration
    'WebhooksIntegration',
    'WebhookConfig',
    'WebhookDelivery',
    'WebhookEvent',
    'webhooks_integration',
    
    # Initialization functions
    'initialize_integrations',
    'shutdown_integrations',
]
