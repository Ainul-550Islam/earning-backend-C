"""
Import Fix Module for Tenant System

This module provides corrected imports and resolves circular dependencies
for the improved tenant system files.
"""

import sys
import os
from pathlib import Path

# Add the tenant module to Python path for proper imports
tenant_module_path = Path(__file__).parent
sys.path.insert(0, str(tenant_module_path))

# Corrected imports for improved models
def get_tenant_models():
    """Get tenant models with proper import handling."""
    try:
        from .models_improved import (
            Tenant, TenantSettings, TenantBilling, 
            TenantInvoice, TenantAuditLog
        )
        return Tenant, TenantSettings, TenantBilling, TenantInvoice, TenantAuditLog
    except ImportError:
        # Fallback to original models if improved models not available
        from .models import (
            Tenant, TenantSettings, TenantBilling, 
            TenantInvoice
        )
        return Tenant, TenantSettings, TenantBilling, TenantInvoice, None

# Corrected imports for services
def get_tenant_services():
    """Get tenant services with proper import handling."""
    try:
        from .services_improved import (
            TenantService, TenantSettingsService, 
            TenantBillingService, TenantSecurityService
        )
        return TenantService, TenantSettingsService, TenantBillingService, TenantSecurityService
    except ImportError:
        # Fallback services
        return None, None, None, None

# Corrected imports for permissions
def get_tenant_permissions():
    """Get tenant permissions with proper import handling."""
    try:
        from .permissions_improved import (
            IsTenantOwner, IsTenantMember, IsActiveTenant,
            IsNotSuspended, HasValidSubscription, IsSuperadminOrOwner
        )
        return (IsTenantOwner, IsTenantMember, IsActiveTenant,
                IsNotSuspended, HasValidSubscription, IsSuperadminOrOwner)
    except ImportError:
        from .permissions import IsTenantOwner, IsTenantMember
        return IsTenantOwner, IsTenantMember, None, None, None, None

# Corrected imports for serializers
def get_tenant_serializers():
    """Get tenant serializers with proper import handling."""
    try:
        from .serializers_improved import (
            TenantSerializer, TenantSettingsSerializer,
            TenantBillingSerializer, TenantInvoiceSerializer
        )
        return TenantSerializer, TenantSettingsSerializer, TenantBillingSerializer, TenantInvoiceSerializer
    except ImportError:
        from .serializers import (
            TenantSerializer, TenantSettingsSerializer,
            TenantBillingSerializer
        )
        return TenantSerializer, TenantSettingsSerializer, TenantBillingSerializer, None

# Model aliases for backward compatibility
def setup_model_aliases():
    """Setup model aliases for backward compatibility."""
    Tenant, TenantSettings, TenantBilling, TenantInvoice, TenantAuditLog = get_tenant_models()
    
    # Create aliases in module namespace
    sys.modules[__name__].Tenant = Tenant
    sys.modules[__name__].TenantSettings = TenantSettings
    sys.modules[__name__].TenantBilling = TenantBilling
    sys.modules[__name__].TenantInvoice = TenantInvoice
    if TenantAuditLog:
        sys.modules[__name__].TenantAuditLog = TenantAuditLog

# Import utilities
def safe_import(module_name, fallback=None):
    """Safely import a module with fallback."""
    try:
        return __import__(module_name, fromlist=[''])
    except ImportError:
        return fallback

# Lazy import decorator
def lazy_import(module_path, attribute_name):
    """Create a lazy import for circular dependency resolution."""
    class LazyImport:
        def __init__(self):
            self._module = None
            self._attribute = None
        
        def __getattr__(self, name):
            if self._module is None:
                self._module = __import__(module_path, fromlist=[attribute_name])
                self._attribute = getattr(self._module, attribute_name)
            return getattr(self._attribute, name)
    
    return LazyImport()

# Specific lazy imports for common circular dependencies
TenantService = lazy_import('.services_improved', 'TenantService')
TenantSecurityService = lazy_import('.services_improved', 'TenantSecurityService')

# Initialize model aliases
setup_model_aliases()

# Export clean imports
__all__ = [
    'get_tenant_models',
    'get_tenant_services', 
    'get_tenant_permissions',
    'get_tenant_serializers',
    'setup_model_aliases',
    'safe_import',
    'lazy_import',
    'TenantService',
    'TenantSecurityService'
]
