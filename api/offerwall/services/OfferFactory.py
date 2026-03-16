"""
Offer Factory - Factory pattern for creating offer processors
"""
import logging
from typing import Type, Dict, Optional
from .OfferProcessor import OfferProcessor
from ..constants import *
from ..exceptions import InvalidProviderConfigException

logger = logging.getLogger(__name__)


class OfferFactory:
    """
    Factory class for creating offer processor instances
    
    Usage:
        factory = OfferFactory()
        processor = factory.create_processor(provider)
        offers = processor.sync_offers()
    """
    
    # Registry of processor classes
    _processors: Dict[str, Type[OfferProcessor]] = {}
    
    @classmethod
    def register_processor(cls, provider_type: str, processor_class: Type[OfferProcessor]) -> None:
        """
        Register a processor class for a provider type
        
        Args:
            provider_type: Provider type identifier (e.g., 'tapjoy', 'adgem')
            processor_class: Processor class to register
        
        Example:
            OfferFactory.register_processor('tapjoy', TapjoyService)
        """
        if not issubclass(processor_class, OfferProcessor):
            raise ValueError(
                f"{processor_class.__name__} must be a subclass of OfferProcessor"
            )
        
        cls._processors[provider_type] = processor_class
        logger.info(f"Registered processor: {provider_type} -> {processor_class.__name__}")
    
    @classmethod
    def unregister_processor(cls, provider_type: str) -> None:
        """
        Unregister a processor
        
        Args:
            provider_type: Provider type to unregister
        """
        if provider_type in cls._processors:
            del cls._processors[provider_type]
            logger.info(f"Unregistered processor: {provider_type}")
    
    @classmethod
    def get_processor_class(cls, provider_type: str) -> Optional[Type[OfferProcessor]]:
        """
        Get processor class for provider type
        
        Args:
            provider_type: Provider type
        
        Returns:
            Processor class or None if not found
        """
        return cls._processors.get(provider_type)
    
    @classmethod
    def create_processor(cls, provider) -> OfferProcessor:
        """
        Create processor instance for provider
        
        Args:
            provider: OfferProvider instance
        
        Returns:
            OfferProcessor instance
        
        Raises:
            InvalidProviderConfigException: If processor not found for provider type
        
        Example:
            provider = OfferProvider.objects.get(name='Tapjoy')
            processor = OfferFactory.create_processor(provider)
        """
        processor_class = cls._processors.get(provider.provider_type)
        
        if not processor_class:
            available = ', '.join(cls._processors.keys())
            raise InvalidProviderConfigException(
                f"No processor registered for provider type: {provider.provider_type}. "
                f"Available types: {available}"
            )
        
        logger.info(
            f"Creating processor: {processor_class.__name__} for {provider.name}"
        )
        
        return processor_class(provider)
    
    @classmethod
    def get_available_providers(cls) -> list:
        """
        Get list of available provider types
        
        Returns:
            List of registered provider type strings
        """
        return list(cls._processors.keys())
    
    @classmethod
    def is_provider_supported(cls, provider_type: str) -> bool:
        """
        Check if provider type is supported
        
        Args:
            provider_type: Provider type to check
        
        Returns:
            True if supported, False otherwise
        """
        return provider_type in cls._processors
    
    @classmethod
    def get_processor_info(cls) -> Dict[str, str]:
        """
        Get information about all registered processors
        
        Returns:
            Dictionary mapping provider type to processor class name
        """
        return {
            provider_type: processor_class.__name__
            for provider_type, processor_class in cls._processors.items()
        }
    
    @classmethod
    def bulk_create_processors(cls, providers: list) -> Dict[str, OfferProcessor]:
        """
        Create processors for multiple providers
        
        Args:
            providers: List of OfferProvider instances
        
        Returns:
            Dictionary mapping provider name to processor instance
        """
        processors = {}
        
        for provider in providers:
            try:
                processor = cls.create_processor(provider)
                processors[provider.name] = processor
            except InvalidProviderConfigException as e:
                logger.error(f"Failed to create processor for {provider.name}: {e}")
        
        return processors
    
    @classmethod
    def sync_all_providers(cls, providers: list = None) -> Dict[str, dict]:
        """
        Sync offers from all providers
        
        Args:
            providers: List of providers to sync (optional)
        
        Returns:
            Dictionary mapping provider name to sync results
        """
        from ..models import OfferProvider
        
        if providers is None:
            providers = OfferProvider.objects.filter(
                status='active',
                auto_sync=True
            )
        
        results = {}
        
        for provider in providers:
            try:
                processor = cls.create_processor(provider)
                sync_result = processor.sync_offers()
                results[provider.name] = sync_result
                
                logger.info(
                    f"Synced {provider.name}: "
                    f"{sync_result.get('synced', 0)} offers"
                )
            
            except Exception as e:
                logger.error(f"Failed to sync {provider.name}: {e}")
                results[provider.name] = {
                    'success': False,
                    'error': str(e)
                }
        
        return results
    
    @classmethod
    def validate_provider_config(cls, provider) -> tuple:
        """
        Validate provider configuration
        
        Args:
            provider: OfferProvider instance
        
        Returns:
            Tuple of (is_valid: bool, errors: list)
        """
        errors = []
        
        # Check if provider type is supported
        if not cls.is_provider_supported(provider.provider_type):
            errors.append(
                f"Provider type '{provider.provider_type}' is not supported"
            )
            return False, errors
        
        # Check required fields
        if not provider.api_key:
            errors.append("API key is required")
        
        if not provider.api_base_url:
            errors.append("API base URL is required")
        
        # Provider-specific validation
        if provider.provider_type in [PROVIDER_TAPJOY, PROVIDER_ADGEM]:
            if not provider.app_id:
                errors.append("App ID is required")
        
        if provider.provider_type == PROVIDER_ADGATE:
            if not provider.app_id:  # wall_code
                errors.append("Wall code is required")
        
        # Check status
        if provider.status not in ['active', 'testing']:
            errors.append(
                f"Provider must be 'active' or 'testing' (current: {provider.status})"
            )
        
        is_valid = len(errors) == 0
        
        return is_valid, errors
    
    @classmethod
    def get_provider_capabilities(cls, provider_type: str) -> Dict[str, bool]:
        """
        Get capabilities of a provider type
        
        Args:
            provider_type: Provider type
        
        Returns:
            Dictionary of capabilities
        """
        # Default capabilities
        capabilities = {
            'supports_sync': True,
            'supports_webhook': True,
            'supports_targeting': True,
            'supports_categories': True,
            'supports_video': False,
            'supports_surveys': False,
        }
        
        # Provider-specific capabilities
        if provider_type == PROVIDER_PERSONA:
            capabilities['supports_surveys'] = True
            capabilities['supports_sync'] = False  # No API for listing
        
        if provider_type == PROVIDER_TAPJOY:
            capabilities['supports_video'] = True
        
        return capabilities
    
    @classmethod
    def reset_registry(cls) -> None:
        """
        Clear all registered processors (useful for testing)
        """
        cls._processors.clear()
        logger.warning("Processor registry cleared")


# Auto-register all available processors
def auto_register_processors():
    """
    Automatically register all available processor classes
    """
    try:
        from .TapjoyService import TapjoyService
        OfferFactory.register_processor(PROVIDER_TAPJOY, TapjoyService)
    except ImportError:
        logger.warning("TapjoyService not available")
    
    try:
        from .AdGemService import AdGemService
        OfferFactory.register_processor(PROVIDER_ADGEM, AdGemService)
    except ImportError:
        logger.warning("AdGemService not available")
    
    try:
        from .AdGateService import AdGateService
        OfferFactory.register_processor(PROVIDER_ADGATE, AdGateService)
    except ImportError:
        logger.warning("AdGateService not available")
    
    try:
        from .OfferwallService import OfferwallService
        OfferFactory.register_processor(PROVIDER_OFFERWALL, OfferwallService)
    except ImportError:
        logger.warning("OfferwallService not available")
    
    try:
        from .PersonaService import PersonaService
        OfferFactory.register_processor(PROVIDER_PERSONA, PersonaService)
    except ImportError:
        logger.warning("PersonaService not available")


# Auto-register on module import
auto_register_processors()


# Convenience function
def create_processor(provider):
    """
    Convenience function to create processor
    
    Args:
        provider: OfferProvider instance
    
    Returns:
        OfferProcessor instance
    """
    return OfferFactory.create_processor(provider)