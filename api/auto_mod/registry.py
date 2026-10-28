# =============================================================================
# auto_mod/registry.py
# =============================================================================

"""
Registry system for auto moderation.
Provides centralized registration and discovery of components.
"""

import logging
from typing import Any, Dict, List, Optional, Type, Union
from datetime import datetime
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class ComponentRegistry:
    """Base registry for components."""
    
    def __init__(self, name: str):
        self.name = name
        self._registry = {}
        self._metadata = {}
    
    def register(self, key: str, component: Any, metadata: Dict[str, Any] = None) -> bool:
        """
        Register a component.
        
        Args:
            key: Component key
            component: Component instance
            metadata: Component metadata
            
        Returns:
            True if registered successfully
        """
        try:
            if key in self._registry:
                logger.warning(f"Component {key} already registered in {self.name}")
                return False
            
            self._registry[key] = component
            self._metadata[key] = metadata or {}
            
            logger.info(f"Registered component {key} in {self.name}")
            return True
            
        except Exception as exc:
            logger.error(f"Register component failed: {exc}")
            return False
    
    def unregister(self, key: str) -> bool:
        """
        Unregister a component.
        
        Args:
            key: Component key
            
        Returns:
            True if unregistered successfully
        """
        try:
            if key not in self._registry:
                logger.warning(f"Component {key} not found in {self.name}")
                return False
            
            del self._registry[key]
            del self._metadata[key]
            
            logger.info(f"Unregistered component {key} from {self.name}")
            return True
            
        except Exception as exc:
            logger.error(f"Unregister component failed: {exc}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get component by key.
        
        Args:
            key: Component key
            
        Returns:
            Component instance or None
        """
        return self._registry.get(key)
    
    def get_all(self) -> Dict[str, Any]:
        """Get all registered components."""
        return self._registry.copy()
    
    def get_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get component metadata.
        
        Args:
            key: Component key
            
        Returns:
            Metadata dictionary or None
        """
        return self._metadata.get(key)
    
    def list_keys(self) -> List[str]:
        """Get list of all registered keys."""
        return list(self._registry.keys())
    
    def is_registered(self, key: str) -> bool:
        """Check if component is registered."""
        return key in self._registry
    
    def clear(self) -> None:
        """Clear all registered components."""
        self._registry.clear()
        self._metadata.clear()
        logger.info(f"Cleared all components from {self.name}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            'name': self.name,
            'total_components': len(self._registry),
            'registered_keys': list(self._registry.keys()),
            'last_updated': timezone.now().isoformat(),
        }


class ScannerRegistry(ComponentRegistry):
    """Registry for content scanners."""
    
    def __init__(self):
        super().__init__("scanners")
    
    def register_scanner(self, name: str, scanner_class: Type, 
                        content_types: List[str], metadata: Dict[str, Any] = None) -> bool:
        """
        Register a scanner class.
        
        Args:
            name: Scanner name
            scanner_class: Scanner class
            content_types: Supported content types
            metadata: Additional metadata
            
        Returns:
            True if registered successfully
        """
        scanner_metadata = {
            'content_types': content_types,
            'class_name': scanner_class.__name__,
            'module': scanner_class.__module__,
            'registered_at': timezone.now().isoformat(),
        }
        
        if metadata:
            scanner_metadata.update(metadata)
        
        return self.register(name, scanner_class, scanner_metadata)
    
    def get_scanners_for_content_type(self, content_type: str) -> List[Any]:
        """
        Get scanners that support a specific content type.
        
        Args:
            content_type: Content type
            
        Returns:
            List of scanner classes
        """
        compatible_scanners = []
        
        for key, metadata in self._metadata.items():
            content_types = metadata.get('content_types', [])
            if content_type in content_types:
                compatible_scanners.append(self._registry[key])
        
        return compatible_scanners


class AnalyzerRegistry(ComponentRegistry):
    """Registry for content analyzers."""
    
    def __init__(self):
        super().__init__("analyzers")
    
    def register_analyzer(self, name: str, analyzer_class: Type,
                         analyzer_type: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Register an analyzer class.
        
        Args:
            name: Analyzer name
            analyzer_class: Analyzer class
            analyzer_type: Type of analyzer
            metadata: Additional metadata
            
        Returns:
            True if registered successfully
        """
        analyzer_metadata = {
            'analyzer_type': analyzer_type,
            'class_name': analyzer_class.__name__,
            'module': analyzer_class.__module__,
            'registered_at': timezone.now().isoformat(),
        }
        
        if metadata:
            analyzer_metadata.update(metadata)
        
        return self.register(name, analyzer_class, analyzer_metadata)
    
    def get_analyzers_by_type(self, analyzer_type: str) -> List[Any]:
        """
        Get analyzers of a specific type.
        
        Args:
            analyzer_type: Type of analyzer
            
        Returns:
            List of analyzer classes
        """
        type_analyzers = []
        
        for key, metadata in self._metadata.items():
            if metadata.get('analyzer_type') == analyzer_type:
                type_analyzers.append(self._registry[key])
        
        return type_analyzers


class FilterRegistry(ComponentRegistry):
    """Registry for content filters."""
    
    def __init__(self):
        super().__init__("filters")
    
    def register_filter(self, name: str, filter_class: Type,
                       filter_type: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Register a filter class.
        
        Args:
            name: Filter name
            filter_class: Filter class
            filter_type: Type of filter
            metadata: Additional metadata
            
        Returns:
            True if registered successfully
        """
        filter_metadata = {
            'filter_type': filter_type,
            'class_name': filter_class.__name__,
            'module': filter_class.__module__,
            'registered_at': timezone.now().isoformat(),
        }
        
        if metadata:
            filter_metadata.update(metadata)
        
        return self.register(name, filter_class, filter_metadata)
    
    def get_filters_by_type(self, filter_type: str) -> List[Any]:
        """
        Get filters of a specific type.
        
        Args:
            filter_type: Type of filter
            
        Returns:
            List of filter classes
        """
        type_filters = []
        
        for key, metadata in self._metadata.items():
            if metadata.get('filter_type') == filter_type:
                type_filters.append(self._registry[key])
        
        return type_filters


class NotifierRegistry(ComponentRegistry):
    """Registry for notification systems."""
    
    def __init__(self):
        super().__init__("notifiers")
    
    def register_notifier(self, name: str, notifier_class: Type,
                         notifier_type: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Register a notifier class.
        
        Args:
            name: Notifier name
            notifier_class: Notifier class
            notifier_type: Type of notifier
            metadata: Additional metadata
            
        Returns:
            True if registered successfully
        """
        notifier_metadata = {
            'notifier_type': notifier_type,
            'class_name': notifier_class.__name__,
            'module': notifier_class.__module__,
            'registered_at': timezone.now().isoformat(),
        }
        
        if metadata:
            notifier_metadata.update(metadata)
        
        return self.register(name, notifier_class, notifier_metadata)
    
    def get_notifiers_by_type(self, notifier_type: str) -> List[Any]:
        """
        Get notifiers of a specific type.
        
        Args:
            notifier_type: Type of notifier
            
        Returns:
            List of notifier classes
        """
        type_notifiers = []
        
        for key, metadata in self._metadata.items():
            if metadata.get('notifier_type') == notifier_type:
                type_notifiers.append(self._registry[key])
        
        return type_notifiers


class ReporterRegistry(ComponentRegistry):
    """Registry for reporting systems."""
    
    def __init__(self):
        super().__init__("reporters")
    
    def register_reporter(self, name: str, reporter_class: Type,
                         reporter_type: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Register a reporter class.
        
        Args:
            name: Reporter name
            reporter_class: Reporter class
            reporter_type: Type of reporter
            metadata: Additional metadata
            
        Returns:
            True if registered successfully
        """
        reporter_metadata = {
            'reporter_type': reporter_type,
            'class_name': reporter_class.__name__,
            'module': reporter_class.__module__,
            'registered_at': timezone.now().isoformat(),
        }
        
        if metadata:
            reporter_metadata.update(metadata)
        
        return self.register(name, reporter_class, reporter_metadata)
    
    def get_reporters_by_type(self, reporter_type: str) -> List[Any]:
        """
        Get reporters of a specific type.
        
        Args:
            reporter_type: Type of reporter
            
        Returns:
            List of reporter classes
        """
        type_reporters = []
        
        for key, metadata in self._metadata.items():
            if metadata.get('reporter_type') == reporter_type:
                type_reporters.append(self._registry[key])
        
        return type_reporters


class ValidatorRegistry(ComponentRegistry):
    """Registry for validators."""
    
    def __init__(self):
        super().__init__("validators")
    
    def register_validator(self, name: str, validator_class: Type,
                         validator_type: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Register a validator class.
        
        Args:
            name: Validator name
            validator_class: Validator class
            validator_type: Type of validator
            metadata: Additional metadata
            
        Returns:
            True if registered successfully
        """
        validator_metadata = {
            'validator_type': validator_type,
            'class_name': validator_class.__name__,
            'module': validator_class.__module__,
            'registered_at': timezone.now().isoformat(),
        }
        
        if metadata:
            validator_metadata.update(metadata)
        
        return self.register(name, validator_class, validator_metadata)
    
    def get_validators_by_type(self, validator_type: str) -> List[Any]:
        """
        Get validators of a specific type.
        
        Args:
            validator_type: Type of validator
            
        Returns:
            List of validator classes
        """
        type_validators = []
        
        for key, metadata in self._metadata.items():
            if metadata.get('validator_type') == validator_type:
                type_validators.append(self._registry[key])
        
        return type_validators


class ProcessorRegistry(ComponentRegistry):
    """Registry for data processors."""
    
    def __init__(self):
        super().__init__("processors")
    
    def register_processor(self, name: str, processor_class: Type,
                          processor_type: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Register a processor class.
        
        Args:
            name: Processor name
            processor_class: Processor class
            processor_type: Type of processor
            metadata: Additional metadata
            
        Returns:
            True if registered successfully
        """
        processor_metadata = {
            'processor_type': processor_type,
            'class_name': processor_class.__name__,
            'module': processor_class.__module__,
            'registered_at': timezone.now().isoformat(),
        }
        
        if metadata:
            processor_metadata.update(metadata)
        
        return self.register(name, processor_class, processor_metadata)
    
    def get_processors_by_type(self, processor_type: str) -> List[Any]:
        """
        Get processors of a specific type.
        
        Args:
            processor_type: Type of processor
            
        Returns:
            List of processor classes
        """
        type_processors = []
        
        for key, metadata in self._metadata.items():
            if metadata.get('processor_type') == processor_type:
                type_processors.append(self._registry[key])
        
        return type_processors


class TransformerRegistry(ComponentRegistry):
    """Registry for data transformers."""
    
    def __init__(self):
        super().__init__("transformers")
    
    def register_transformer(self, name: str, transformer_class: Type,
                            transformer_type: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Register a transformer class.
        
        Args:
            name: Transformer name
            transformer_class: Transformer class
            transformer_type: Type of transformer
            metadata: Additional metadata
            
        Returns:
            True if registered successfully
        """
        transformer_metadata = {
            'transformer_type': transformer_type,
            'class_name': transformer_class.__name__,
            'module': transformer_class.__module__,
            'registered_at': timezone.now().isoformat(),
        }
        
        if metadata:
            transformer_metadata.update(metadata)
        
        return self.register(name, transformer_class, transformer_metadata)
    
    def get_transformers_by_type(self, transformer_type: str) -> List[Any]:
        """
        Get transformers of a specific type.
        
        Args:
            transformer_type: Type of transformer
            
        Returns:
            List of transformer classes
        """
        type_transformers = []
        
        for key, metadata in self._metadata.items():
            if metadata.get('transformer_type') == transformer_type:
                type_transformers.append(self._registry[key])
        
        return type_transformers


class EnricherRegistry(ComponentRegistry):
    """Registry for data enrichers."""
    
    def __init__(self):
        super().__init__("enrichers")
    
    def register_enricher(self, name: str, enricher_class: Type,
                         enricher_type: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Register an enricher class.
        
        Args:
            name: Enricher name
            enricher_class: Enricher class
            enricher_type: Type of enricher
            metadata: Additional metadata
            
        Returns:
            True if registered successfully
        """
        enricher_metadata = {
            'enricher_type': enricher_type,
            'class_name': enricher_class.__name__,
            'module': enricher_class.__module__,
            'registered_at': timezone.now().isoformat(),
        }
        
        if metadata:
            enricher_metadata.update(metadata)
        
        return self.register(name, enricher_class, enricher_metadata)
    
    def get_enrichers_by_type(self, enricher_type: str) -> List[Any]:
        """
        Get enrichers of a specific type.
        
        Args:
            enricher_type: Type of enricher
            
        Returns:
            List of enricher classes
        """
        type_enrichers = []
        
        for key, metadata in self._metadata.items():
            if metadata.get('enricher_type') == enricher_type:
                type_enrichers.append(self._registry[key])
        
        return type_enrichers


class WorkflowRegistry(ComponentRegistry):
    """Registry for workflows."""
    
    def __init__(self):
        super().__init__("workflows")
    
    def register_workflow(self, name: str, workflow_class: Type,
                         workflow_type: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Register a workflow class.
        
        Args:
            name: Workflow name
            workflow_class: Workflow class
            workflow_type: Type of workflow
            metadata: Additional metadata
            
        Returns:
            True if registered successfully
        """
        workflow_metadata = {
            'workflow_type': workflow_type,
            'class_name': workflow_class.__name__,
            'module': workflow_class.__module__,
            'registered_at': timezone.now().isoformat(),
        }
        
        if metadata:
            workflow_metadata.update(metadata)
        
        return self.register(name, workflow_class, workflow_metadata)
    
    def get_workflows_by_type(self, workflow_type: str) -> List[Any]:
        """
        Get workflows of a specific type.
        
        Args:
            workflow_type: Type of workflow
            
        Returns:
            List of workflow classes
        """
        type_workflows = []
        
        for key, metadata in self._metadata.items():
            if metadata.get('workflow_type') == workflow_type:
                type_workflows.append(self._registry[key])
        
        return type_workflows


class AdapterRegistry(ComponentRegistry):
    """Registry for adapters."""
    
    def __init__(self):
        super().__init__("adapters")
    
    def register_adapter(self, name: str, adapter_class: Type,
                        adapter_type: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Register an adapter class.
        
        Args:
            name: Adapter name
            adapter_class: Adapter class
            adapter_type: Type of adapter
            metadata: Additional metadata
            
        Returns:
            True if registered successfully
        """
        adapter_metadata = {
            'adapter_type': adapter_type,
            'class_name': adapter_class.__name__,
            'module': adapter_class.__module__,
            'registered_at': timezone.now().isoformat(),
        }
        
        if metadata:
            adapter_metadata.update(metadata)
        
        return self.register(name, adapter_class, adapter_metadata)
    
    def get_adapters_by_type(self, adapter_type: str) -> List[Any]:
        """
        Get adapters of a specific type.
        
        Args:
            adapter_type: Type of adapter
            
        Returns:
            List of adapter classes
        """
        type_adapters = []
        
        for key, metadata in self._metadata.items():
            if metadata.get('adapter_type') == adapter_type:
                type_adapters.append(self._registry[key])
        
        return type_adapters


class EventHandlerRegistry(ComponentRegistry):
    """Registry for event handlers."""
    
    def __init__(self):
        super().__init__("event_handlers")
    
    def register_handler(self, name: str, handler_class: Type,
                         event_type: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Register an event handler class.
        
        Args:
            name: Handler name
            handler_class: Handler class
            event_type: Type of event
            metadata: Additional metadata
            
        Returns:
            True if registered successfully
        """
        handler_metadata = {
            'event_type': event_type,
            'class_name': handler_class.__name__,
            'module': handler_class.__module__,
            'registered_at': timezone.now().isoformat(),
        }
        
        if metadata:
            handler_metadata.update(metadata)
        
        return self.register(name, handler_class, handler_metadata)
    
    def get_handlers_by_event_type(self, event_type: str) -> List[Any]:
        """
        Get handlers for a specific event type.
        
        Args:
            event_type: Type of event
            
        Returns:
            List of handler classes
        """
        type_handlers = []
        
        for key, metadata in self._metadata.items():
            if metadata.get('event_type') == event_type:
                type_handlers.append(self._registry[key])
        
        return type_handlers


class ServiceRegistry(ComponentRegistry):
    """Registry for services."""
    
    def __init__(self):
        super().__init__("services")
    
    def register_service(self, name: str, service_class: Type,
                         service_type: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Register a service class.
        
        Args:
            name: Service name
            service_class: Service class
            service_type: Type of service
            metadata: Additional metadata
            
        Returns:
            True if registered successfully
        """
        service_metadata = {
            'service_type': service_type,
            'class_name': service_class.__name__,
            'module': service_class.__module__,
            'registered_at': timezone.now().isoformat(),
        }
        
        if metadata:
            service_metadata.update(metadata)
        
        return self.register(name, service_class, service_metadata)
    
    def get_services_by_type(self, service_type: str) -> List[Any]:
        """
        Get services of a specific type.
        
        Args:
            service_type: Type of service
            
        Returns:
            List of service classes
        """
        type_services = []
        
        for key, metadata in self._metadata.items():
            if metadata.get('service_type') == service_type:
                type_services.append(self._registry[key])
        
        return type_services


class MasterRegistry:
    """Master registry that manages all component registries."""
    
    def __init__(self):
        self.registries = {
            'scanners': ScannerRegistry(),
            'analyzers': AnalyzerRegistry(),
            'filters': FilterRegistry(),
            'notifiers': NotifierRegistry(),
            'reporters': ReporterRegistry(),
            'validators': ValidatorRegistry(),
            'processors': ProcessorRegistry(),
            'transformers': TransformerRegistry(),
            'enrichers': EnricherRegistry(),
            'workflows': WorkflowRegistry(),
            'adapters': AdapterRegistry(),
            'event_handlers': EventHandlerRegistry(),
            'services': ServiceRegistry(),
        }
    
    def get_registry(self, registry_name: str) -> Optional[ComponentRegistry]:
        """
        Get a specific registry.
        
        Args:
            registry_name: Name of registry
            
        Returns:
            Registry instance or None
        """
        return self.registries.get(registry_name)
    
    def get_all_registries(self) -> Dict[str, ComponentRegistry]:
        """Get all registries."""
        return self.registries.copy()
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get statistics for all registries."""
        stats = {}
        
        for name, registry in self.registries.items():
            stats[name] = registry.get_stats()
        
        return stats
    
    def clear_all_registries(self) -> None:
        """Clear all registries."""
        for registry in self.registries.values():
            registry.clear()
        
        logger.info("Cleared all registries")
    
    def get_component_count(self) -> int:
        """Get total number of registered components."""
        total = 0
        
        for registry in self.registries.values():
            total += len(registry._registry)
        
        return total


# Global registry instances
master_registry = MasterRegistry()

# Individual registry instances for easy access
scanner_registry = master_registry.get_registry('scanners')
analyzer_registry = master_registry.get_registry('analyzers')
filter_registry = master_registry.get_registry('filters')
notifier_registry = master_registry.get_registry('notifiers')
reporter_registry = master_registry.get_registry('reporters')
validator_registry = master_registry.get_registry('validators')
processor_registry = master_registry.get_registry('processors')
transformer_registry = master_registry.get_registry('transformers')
enricher_registry = master_registry.get_registry('enrichers')
workflow_registry = master_registry.get_registry('workflows')
adapter_registry = master_registry.get_registry('adapters')
event_handler_registry = master_registry.get_registry('event_handlers')
service_registry = master_registry.get_registry('services')


# Utility functions
def register_scanner(name: str, scanner_class: Type, 
                    content_types: List[str], metadata: Dict[str, Any] = None) -> bool:
    """Register a scanner."""
    return scanner_registry.register_scanner(name, scanner_class, content_types, metadata)


def register_analyzer(name: str, analyzer_class: Type,
                     analyzer_type: str, metadata: Dict[str, Any] = None) -> bool:
    """Register an analyzer."""
    return analyzer_registry.register_analyzer(name, analyzer_class, analyzer_type, metadata)


def register_filter(name: str, filter_class: Type,
                   filter_type: str, metadata: Dict[str, Any] = None) -> bool:
    """Register a filter."""
    return filter_registry.register_filter(name, filter_class, filter_type, metadata)


def register_notifier(name: str, notifier_class: Type,
                     notifier_type: str, metadata: Dict[str, Any] = None) -> bool:
    """Register a notifier."""
    return notifier_registry.register_notifier(name, notifier_class, notifier_type, metadata)


def get_registry_stats() -> Dict[str, Any]:
    """Get registry statistics."""
    return master_registry.get_registry_stats()


# Initialize logging
logger.info("Registry module initialized with component registration system")
