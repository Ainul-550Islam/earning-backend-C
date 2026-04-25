"""
api/ad_networks/services/base.py
Base service class for all services
SaaS-ready with tenant support
"""

import logging
from abc import ABC
from django.db import models


class BaseService(ABC):
    """Base service class with common functionality"""
    
    def __init__(self, tenant_id=None):
        self.tenant_id = tenant_id or 'default'
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def set_tenant_id(self, tenant_id):
        """Set tenant ID for the service"""
        self.tenant_id = tenant_id
    
    def get_tenant_id(self):
        """Get current tenant ID"""
        return self.tenant_id
    
    def log_error(self, message, exception=None):
        """Log error with exception details"""
        if exception:
            self.logger.error(f"{message}: {str(exception)}", exc_info=True)
        else:
            self.logger.error(message)
    
    def log_info(self, message):
        """Log info message"""
        self.logger.info(message)
    
    def log_warning(self, message):
        """Log warning message"""
        self.logger.warning(message)
    
    def log_debug(self, message):
        """Log debug message"""
        self.logger.debug(message)
