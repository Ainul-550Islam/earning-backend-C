"""
Integration signals for alerts app - Event-driven integration communication
"""
from django.dispatch import Signal, receiver
from django.db.models.signals import post_save, post_delete, pre_save
from django.utils import timezone
from django.contrib.auth import get_user_model
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Integration system signals
integration_connected = Signal()
integration_disconnected = Signal()
integration_data_sent = Signal()
integration_data_received = Signal()
integration_error = Signal()
integration_health_check = Signal()
integration_config_updated = Signal()
integration_registered = Signal()
integration_unregistered = Signal()

# Data flow signals
data_flow_started = Signal()
data_flow_completed = Signal()
data_flow_failed = Signal()
data_flow_retry = Signal()
data_flow_transformed = Signal()
data_flow_validated = Signal()

# System integration signals
system_sync_started = Signal()
system_sync_completed = Signal()
system_sync_failed = Signal()
system_backup_started = Signal()
system_backup_completed = Signal()
system_restore_started = Signal()
system_restore_completed = Signal()

# Performance monitoring signals
integration_performance = Signal()
throughput_monitored = Signal()
latency_monitored = Signal()
error_rate_monitored = Signal()


class IntegrationSignalManager:
    """Manager for integration signal handling"""
    
    def __init__(self):
        self.active_integrations = {}
        self.signal_handlers = {}
        self.performance_metrics = {}
    
    def register_integration(self, integration_name: str, integration_handler):
        """Register integration and set up signal handlers"""
        self.active_integrations[integration_name] = integration_handler
        
        # Set up signal handlers for this integration
        self._setup_integration_handlers(integration_name, integration_handler)
        
        # Trigger registration signal
        integration_registered.send(
            sender=self,
            integration_name=integration_name,
            integration_handler=integration_handler,
            timestamp=timezone.now().isoformat()
        )
        
        logger.info(f"Registered integration: {integration_name}")
    
    def unregister_integration(self, integration_name: str):
        """Unregister integration and clean up signal handlers"""
        if integration_name in self.active_integrations:
            # Clean up signal handlers
            self._cleanup_integration_handlers(integration_name)
            
            # Remove from active integrations
            del self.active_integrations[integration_name]
            
            # Trigger unregistration signal
            integration_unregistered.send(
                sender=self,
                integration_name=integration_name,
                timestamp=timezone.now().isoformat()
            )
            
            logger.info(f"Unregistered integration: {integration_name}")
    
    def _setup_integration_handlers(self, integration_name: str, integration_handler):
        """Set up signal handlers for integration"""
        # Store handlers for cleanup
        self.signal_handlers[integration_name] = []
        
        # Connection handler
        @receiver(integration_connected)
        def handle_connection(sender, **kwargs):
            if kwargs.get('integration_name') == integration_name:
                self._handle_integration_connected(integration_name, **kwargs)
        
        # Disconnection handler
        @receiver(integration_disconnected)
        def handle_disconnection(sender, **kwargs):
            if kwargs.get('integration_name') == integration_name:
                self._handle_integration_disconnected(integration_name, **kwargs)
        
        # Data sent handler
        @receiver(integration_data_sent)
        def handle_data_sent(sender, **kwargs):
            if kwargs.get('integration_name') == integration_name:
                self._handle_data_sent(integration_name, **kwargs)
        
        # Data received handler
        @receiver(integration_data_received)
        def handle_data_received(sender, **kwargs):
            if kwargs.get('integration_name') == integration_name:
                self._handle_data_received(integration_name, **kwargs)
        
        # Error handler
        @receiver(integration_error)
        def handle_error(sender, **kwargs):
            if kwargs.get('integration_name') == integration_name:
                self._handle_integration_error(integration_name, **kwargs)
        
        # Health check handler
        @receiver(integration_health_check)
        def handle_health_check(sender, **kwargs):
            if kwargs.get('integration_name') == integration_name:
                self._handle_health_check(integration_name, **kwargs)
        
        # Store handler references
        self.signal_handlers[integration_name].extend([
            handle_connection, handle_disconnection, handle_data_sent,
            handle_data_received, handle_error, handle_health_check
        ])
    
    def _cleanup_integration_handlers(self, integration_name: str):
        """Clean up signal handlers for integration"""
        if integration_name in self.signal_handlers:
            # In Django, signal handlers are automatically cleaned up
            # when the module is unloaded, but we can track them
            del self.signal_handlers[integration_name]
    
    def _handle_integration_connected(self, integration_name: str, **kwargs):
        """Handle integration connection event"""
        logger.info(f"Integration {integration_name} connected")
        
        # Update integration status
        if integration_name in self.active_integrations:
            integration = self.active_integrations[integration_name]
            integration.last_connected = timezone.now()
            integration.connection_count = getattr(integration, 'connection_count', 0) + 1
        
        # Trigger data flow started
        data_flow_started.send(
            sender=self,
            integration_name=integration_name,
            flow_type='connection',
            timestamp=timezone.now().isoformat()
        )
    
    def _handle_integration_disconnected(self, integration_name: str, **kwargs):
        """Handle integration disconnection event"""
        logger.info(f"Integration {integration_name} disconnected")
        
        # Update integration status
        if integration_name in self.active_integrations:
            integration = self.active_integrations[integration_name]
            integration.last_disconnected = timezone.now()
    
    def _handle_data_sent(self, integration_name: str, **kwargs):
        """Handle data sent event"""
        data_size = kwargs.get('data_size', 0)
        success = kwargs.get('success', False)
        
        # Update performance metrics
        if integration_name not in self.performance_metrics:
            self.performance_metrics[integration_name] = {
                'data_sent': 0,
                'data_received': 0,
                'errors': 0,
                'last_activity': timezone.now()
            }
        
        metrics = self.performance_metrics[integration_name]
        metrics['data_sent'] += data_size
        metrics['last_activity'] = timezone.now()
        
        if not success:
            metrics['errors'] += 1
        
        # Trigger performance monitoring
        integration_performance.send(
            sender=self,
            integration_name=integration_name,
            metric_type='data_sent',
            value=data_size,
            success=success,
            timestamp=timezone.now().isoformat()
        )
    
    def _handle_data_received(self, integration_name: str, **kwargs):
        """Handle data received event"""
        data_size = kwargs.get('data_size', 0)
        data_count = kwargs.get('data_count', 0)
        
        # Update performance metrics
        if integration_name not in self.performance_metrics:
            self.performance_metrics[integration_name] = {
                'data_sent': 0,
                'data_received': 0,
                'errors': 0,
                'last_activity': timezone.now()
            }
        
        metrics = self.performance_metrics[integration_name]
        metrics['data_received'] += data_size
        metrics['last_activity'] = timezone.now()
        
        # Trigger performance monitoring
        integration_performance.send(
            sender=self,
            integration_name=integration_name,
            metric_type='data_received',
            value=data_size,
            data_count=data_count,
            timestamp=timezone.now().isoformat()
        )
    
    def _handle_integration_error(self, integration_name: str, **kwargs):
        """Handle integration error event"""
        error_type = kwargs.get('error_type', 'unknown')
        error_message = kwargs.get('error_message', '')
        
        logger.error(f"Integration {integration_name} error: {error_type} - {error_message}")
        
        # Update error metrics
        if integration_name not in self.performance_metrics:
            self.performance_metrics[integration_name] = {
                'data_sent': 0,
                'data_received': 0,
                'errors': 0,
                'last_activity': timezone.now()
            }
        
        self.performance_metrics[integration_name]['errors'] += 1
        
        # Trigger data flow failed
        data_flow_failed.send(
            sender=self,
            integration_name=integration_name,
            error_type=error_type,
            error_message=error_message,
            timestamp=timezone.now().isoformat()
        )
    
    def _handle_health_check(self, integration_name: str, **kwargs):
        """Handle health check event"""
        is_healthy = kwargs.get('healthy', False)
        response_time = kwargs.get('response_time', 0)
        
        # Update health status
        if integration_name in self.active_integrations:
            integration = self.active_integrations[integration_name]
            integration.last_health_check = timezone.now()
            integration.is_healthy = is_healthy
            integration.last_response_time = response_time
        
        # Trigger performance monitoring
        integration_performance.send(
            sender=self,
            integration_name=integration_name,
            metric_type='health_check',
            value=response_time,
            healthy=is_healthy,
            timestamp=timezone.now().isoformat()
        )
    
    def get_integration_status(self, integration_name: str) -> Optional[Dict[str, Any]]:
        """Get current status of integration"""
        if integration_name not in self.active_integrations:
            return None
        
        integration = self.active_integrations[integration_name]
        metrics = self.performance_metrics.get(integration_name, {})
        
        return {
            'name': integration_name,
            'connected': getattr(integration, 'is_connected', False),
            'healthy': getattr(integration, 'is_healthy', False),
            'last_connected': getattr(integration, 'last_connected', None),
            'last_disconnected': getattr(integration, 'last_disconnected', None),
            'last_health_check': getattr(integration, 'last_health_check', None),
            'last_response_time': getattr(integration, 'last_response_time', 0),
            'connection_count': getattr(integration, 'connection_count', 0),
            'data_sent': metrics.get('data_sent', 0),
            'data_received': metrics.get('data_received', 0),
            'errors': metrics.get('errors', 0),
            'last_activity': metrics.get('last_activity', None)
        }
    
    def get_all_integrations_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all integrations"""
        status = {}
        for integration_name in self.active_integrations:
            status[integration_name] = self.get_integration_status(integration_name)
        return status


class DataFlowSignalManager:
    """Manager for data flow signals"""
    
    def __init__(self):
        self.active_flows = {}
        self.flow_metrics = {}
    
    def start_data_flow(self, flow_id: str, flow_type: str, source: str, destination: str):
        """Start a data flow"""
        flow_info = {
            'flow_id': flow_id,
            'flow_type': flow_type,
            'source': source,
            'destination': destination,
            'started_at': timezone.now(),
            'status': 'running',
            'steps_completed': 0,
            'total_steps': 0
        }
        
        self.active_flows[flow_id] = flow_info
        
        # Trigger flow started signal
        data_flow_started.send(
            sender=self,
            flow_id=flow_id,
            flow_type=flow_type,
            source=source,
            destination=destination,
            timestamp=timezone.now().isoformat()
        )
        
        logger.info(f"Data flow started: {flow_id} ({flow_type})")
    
    def complete_data_flow(self, flow_id: str, result: Dict[str, Any] = None):
        """Complete a data flow"""
        if flow_id not in self.active_flows:
            logger.warning(f"Data flow {flow_id} not found")
            return
        
        flow = self.active_flows[flow_id]
        flow['status'] = 'completed'
        flow['completed_at'] = timezone.now()
        flow['result'] = result
        
        # Calculate duration
        duration = flow['completed_at'] - flow['started_at']
        flow['duration_seconds'] = duration.total_seconds()
        
        # Update metrics
        self._update_flow_metrics(flow_id, flow)
        
        # Trigger flow completed signal
        data_flow_completed.send(
            sender=self,
            flow_id=flow_id,
            flow_type=flow['flow_type'],
            duration_seconds=flow['duration_seconds'],
            result=result,
            timestamp=timezone.now().isoformat()
        )
        
        logger.info(f"Data flow completed: {flow_id} in {flow['duration_seconds']}s")
    
    def fail_data_flow(self, flow_id: str, error: str, error_details: Dict[str, Any] = None):
        """Fail a data flow"""
        if flow_id not in self.active_flows:
            logger.warning(f"Data flow {flow_id} not found")
            return
        
        flow = self.active_flows[flow_id]
        flow['status'] = 'failed'
        flow['failed_at'] = timezone.now()
        flow['error'] = error
        flow['error_details'] = error_details
        
        # Calculate duration
        duration = flow['failed_at'] - flow['started_at']
        flow['duration_seconds'] = duration.total_seconds()
        
        # Trigger flow failed signal
        data_flow_failed.send(
            sender=self,
            flow_id=flow_id,
            flow_type=flow['flow_type'],
            error=error,
            error_details=error_details,
            duration_seconds=flow['duration_seconds'],
            timestamp=timezone.now().isoformat()
        )
        
        logger.error(f"Data flow failed: {flow_id} - {error}")
    
    def retry_data_flow(self, flow_id: str, retry_count: int = 1):
        """Retry a data flow"""
        if flow_id not in self.active_flows:
            logger.warning(f"Data flow {flow_id} not found")
            return
        
        flow = self.active_flows[flow_id]
        flow['retry_count'] = flow.get('retry_count', 0) + 1
        flow['last_retry_at'] = timezone.now()
        
        # Trigger flow retry signal
        data_flow_retry.send(
            sender=self,
            flow_id=flow_id,
            retry_count=flow['retry_count'],
            timestamp=timezone.now().isoformat()
        )
        
        logger.info(f"Data flow retry: {flow_id} (attempt {flow['retry_count']})")
    
    def transform_data_in_flow(self, flow_id: str, transformation_type: str, data_before: Any, data_after: Any):
        """Record data transformation in flow"""
        if flow_id not in self.active_flows:
            logger.warning(f"Data flow {flow_id} not found")
            return
        
        flow = self.active_flows[flow_id]
        flow['steps_completed'] = flow.get('steps_completed', 0) + 1
        
        # Trigger transformation signal
        data_flow_transformed.send(
            sender=self,
            flow_id=flow_id,
            transformation_type=transformation_type,
            data_before=data_before,
            data_after=data_after,
            step_number=flow['steps_completed'],
            timestamp=timezone.now().isoformat()
        )
    
    def validate_data_in_flow(self, flow_id: str, validation_type: str, data: Any, is_valid: bool, errors: List[str] = None):
        """Record data validation in flow"""
        if flow_id not in self.active_flows:
            logger.warning(f"Data flow {flow_id} not found")
            return
        
        flow = self.active_flows[flow_id]
        flow['steps_completed'] = flow.get('steps_completed', 0) + 1
        
        # Trigger validation signal
        data_flow_validated.send(
            sender=self,
            flow_id=flow_id,
            validation_type=validation_type,
            data=data,
            is_valid=is_valid,
            errors=errors or [],
            step_number=flow['steps_completed'],
            timestamp=timezone.now().isoformat()
        )
    
    def _update_flow_metrics(self, flow_id: str, flow_info: Dict[str, Any]):
        """Update flow performance metrics"""
        flow_type = flow_info['flow_type']
        
        if flow_type not in self.flow_metrics:
            self.flow_metrics[flow_type] = {
                'total_flows': 0,
                'completed_flows': 0,
                'failed_flows': 0,
                'average_duration': 0,
                'total_duration': 0
            }
        
        metrics = self.flow_metrics[flow_type]
        metrics['total_flows'] += 1
        metrics['total_duration'] += flow_info['duration_seconds']
        metrics['average_duration'] = metrics['total_duration'] / metrics['total_flows']
        
        if flow_info['status'] == 'completed':
            metrics['completed_flows'] += 1
        elif flow_info['status'] == 'failed':
            metrics['failed_flows'] += 1
    
    def get_flow_metrics(self, flow_type: str = None) -> Dict[str, Any]:
        """Get flow performance metrics"""
        if flow_type:
            return self.flow_metrics.get(flow_type, {})
        return self.flow_metrics.copy()


# Global signal manager instances
integration_signal_manager = IntegrationSignalManager()
data_flow_signal_manager = DataFlowSignalManager()


# Signal utility functions
def trigger_integration_connected(integration_name: str, **kwargs):
    """Trigger integration connected signal"""
    integration_connected.send(
        sender=None,
        integration_name=integration_name,
        timestamp=timezone.now().isoformat(),
        **kwargs
    )


def trigger_integration_disconnected(integration_name: str, **kwargs):
    """Trigger integration disconnected signal"""
    integration_disconnected.send(
        sender=None,
        integration_name=integration_name,
        timestamp=timezone.now().isoformat(),
        **kwargs
    )


def trigger_integration_data_sent(integration_name: str, data: Dict[str, Any], **kwargs):
    """Trigger integration data sent signal"""
    integration_data_sent.send(
        sender=None,
        integration_name=integration_name,
        data=data,
        data_size=len(str(data)),
        timestamp=timezone.now().isoformat(),
        **kwargs
    )


def trigger_integration_data_received(integration_name: str, data: List[Dict[str, Any]], **kwargs):
    """Trigger integration data received signal"""
    integration_data_received.send(
        sender=None,
        integration_name=integration_name,
        data=data,
        data_count=len(data),
        data_size=len(str(data)),
        timestamp=timezone.now().isoformat(),
        **kwargs
    )


def trigger_integration_error(integration_name: str, error_type: str, error_message: str, **kwargs):
    """Trigger integration error signal"""
    integration_error.send(
        sender=None,
        integration_name=integration_name,
        error_type=error_type,
        error_message=error_message,
        timestamp=timezone.now().isoformat(),
        **kwargs
    )


def trigger_system_sync_started(system_name: str, sync_type: str, **kwargs):
    """Trigger system sync started signal"""
    system_sync_started.send(
        sender=None,
        system_name=system_name,
        sync_type=sync_type,
        timestamp=timezone.now().isoformat(),
        **kwargs
    )


def trigger_system_sync_completed(system_name: str, sync_type: str, result: Dict[str, Any], **kwargs):
    """Trigger system sync completed signal"""
    system_sync_completed.send(
        sender=None,
        system_name=system_name,
        sync_type=sync_type,
        result=result,
        timestamp=timezone.now().isoformat(),
        **kwargs
    )


def trigger_system_sync_failed(system_name: str, sync_type: str, error: str, **kwargs):
    """Trigger system sync failed signal"""
    system_sync_failed.send(
        sender=None,
        system_name=system_name,
        sync_type=sync_type,
        error=error,
        timestamp=timezone.now().isoformat(),
        **kwargs
    )


# Initialize signal managers
def initialize_integration_signals():
    """Initialize integration signal system"""
    logger.info("Integration signal system initialized")


# Auto-initialize on module import
try:
    initialize_integration_signals()
except Exception as e:
    logger.error(f"Error initializing integration signals: {e}")
