"""
abstracts.py – Abstract base classes for postback module.

Provides comprehensive abstract base classes including:
- Abstract models
- Abstract services
- Abstract views
- Abstract managers
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from django.db import models
from django.utils import timezone

from .exceptions import PostbackException

logger = logging.getLogger(__name__)


class AbstractBaseModel(models.Model):
    """
    Abstract base model for all postback models.
    
    Provides common fields and functionality that all
    postback models should inherit from.
    """
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    
    class Meta:
        abstract = True
    
    @abstractmethod
    def get_display_name(self) -> str:
        """
        Get human-readable display name for the model instance.
        
        Returns:
            Display name string
        """
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.
        
        Returns:
            Dictionary representation of the model
        """
        data = {}
        
        for field in self._meta.fields:
            field_name = field.name
            field_value = getattr(self, field_name)
            
            # Handle different field types
            if hasattr(field_value, 'isoformat'):
                data[field_name] = field_value.isoformat()
            elif hasattr(field_value, 'id'):
                data[field_name] = str(field_value.id)
            else:
                data[field_name] = field_value
        
        return data


class AbstractPostbackModel(AbstractBaseModel):
    """
    Abstract base class for postback-related models.
    
    Provides common functionality for models that are
    directly related to postback processing.
    """
    
    class Meta:
        abstract = True
    
    @abstractmethod
    def process_postback(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process postback-related data.
        
        Args:
            context: Processing context
            
        Returns:
            Processing result
        """
        pass
    
    @abstractmethod
    def validate_postback_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate postback data.
        
        Args:
            data: Data to validate
            
        Returns:
            True if data is valid
        """
        pass


class AbstractAnalyticsModel(AbstractBaseModel):
    """
    Abstract base class for analytics-related models.
    
    Provides common functionality for models that handle
    analytics and reporting data.
    """
    
    date = models.DateField(db_index=True)
    
    class Meta:
        abstract = True
    
    @abstractmethod
    def calculate_metrics(self) -> Dict[str, Any]:
        """
        Calculate analytics metrics.
        
        Returns:
            Dictionary of calculated metrics
        """
        pass
    
    @abstractmethod
    def get_trend_data(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get trend data for the specified period.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            List of trend data points
        """
        pass


class AbstractConfigModel(AbstractBaseModel):
    """
    Abstract base class for configuration models.
    
    Provides common functionality for models that store
    configuration settings.
    """
    
    is_active = models.BooleanField(default=True, db_index=True)
    
    class Meta:
        abstract = True
    
    @abstractmethod
    def apply_config(self) -> bool:
        """
        Apply configuration settings.
        
        Returns:
            True if configuration was applied successfully
        """
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validate configuration settings.
        
        Returns:
            True if configuration is valid
        """
        pass
    
    def activate(self):
        """Activate the configuration."""
        self.is_active = True
        self.save(update_fields=['is_active'])
    
    def deactivate(self):
        """Deactivate the configuration."""
        self.is_active = False
        self.save(update_fields=['is_active'])


class AbstractBaseService(ABC):
    """
    Abstract base service class.
    
    Provides common interface and functionality that all
    postback services should implement.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._initialized = False
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any] = None):
        """
        Initialize the service.
        
        Args:
            config: Service configuration
        """
        pass
    
    @abstractmethod
    def process(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process data using the service.
        
        Args:
            data: Data to process
            context: Processing context
            
        Returns:
            Processing result
        """
        pass
    
    @abstractmethod
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate data for processing.
        
        Args:
            data: Data to validate
            
        Returns:
            True if data is valid
        """
        pass
    
    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized
    
    def log_operation(self, operation: str, data: Any = None, result: Any = None):
        """Log service operation."""
        log_data = {
            'service': self.__class__.__name__,
            'operation': operation,
            'timestamp': timezone.now().isoformat(),
        }
        
        if data is not None:
            log_data['data_size'] = len(str(data))
        
        if result is not None:
            log_data['result_status'] = 'success' if result else 'failed'
        
        self.logger.info(f"Service operation: {operation} - {log_data}")


class AbstractPostbackService(AbstractBaseService):
    """
    Abstract base class for postback processing services.
    
    Provides common interface for services that handle
    postback processing logic.
    """
    
    @abstractmethod
    def receive_postback(self, postback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receive and process incoming postback.
        
        Args:
            postback_data: Postback data to process
            
        Returns:
            Processing result
        """
        pass
    
    @abstractmethod
    def validate_postback(self, postback_data: Dict[str, Any]) -> bool:
        """
        Validate postback data.
        
        Args:
            postback_data: Postback data to validate
            
        Returns:
            True if postback is valid
        """
        pass
    
    @abstractmethod
    def process_postback(self, postback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process validated postback data.
        
        Args:
            postback_data: Validated postback data
            
        Returns:
            Processing result
        """
        pass


class AbstractAnalyticsService(AbstractBaseService):
    """
    Abstract base class for analytics services.
    
    Provides common interface for services that handle
    analytics and reporting functionality.
    """
    
    @abstractmethod
    def generate_report(self, report_type: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate analytics report.
        
        Args:
            report_type: Type of report to generate
            filters: Report filters
            
        Returns:
            Generated report data
        """
        pass
    
    @abstractmethod
    def calculate_metrics(self, metric_type: str, period: str = 'daily') -> Dict[str, Any]:
        """
        Calculate analytics metrics.
        
        Args:
            metric_type: Type of metrics to calculate
            period: Time period for metrics
            
        Returns:
            Calculated metrics
        """
        pass
    
    @abstractmethod
    def detect_anomalies(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detect anomalies in data.
        
        Args:
            data: Data to analyze
            
        Returns:
            List of detected anomalies
        """
        pass


class AbstractNotificationService(AbstractBaseService):
    """
    Abstract base class for notification services.
    
    Provides common interface for services that handle
    notifications and alerts.
    """
    
    @abstractmethod
    def send_notification(self, notification_type: str, recipients: List[str], data: Dict[str, Any]) -> bool:
        """
        Send notification to recipients.
        
        Args:
            notification_type: Type of notification
            recipients: List of recipient identifiers
            data: Notification data
            
        Returns:
            True if notification was sent successfully
        """
        pass
    
    @abstractmethod
    def create_notification(self, notification_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create notification object.
        
        Args:
            notification_type: Type of notification
            data: Notification data
            
        Returns:
            Created notification object
        """
        pass
    
    @abstractmethod
    def get_notification_history(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Get notification history.
        
        Args:
            filters: History filters
            
        Returns:
            List of notification history records
        """
        pass


class AbstractBaseManager(models.Manager):
    """
    Abstract base manager for postback models.
    
    Provides common manager functionality that all
    postback model managers should inherit from.
    """
    
    @abstractmethod
    def get_active_queryset(self):
        """
        Get queryset of active records.
        
        Returns:
            QuerySet of active records
        """
        pass
    
    @abstractmethod
    def get_by_date_range(self, start_date: datetime, end_date: datetime):
        """
        Get records within date range.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            QuerySet of records in date range
        """
        pass
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get manager statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            'total_count': self.count(),
            'active_count': self.get_active_queryset().count(),
            'model_name': self.model.__name__,
        }


class AbstractPostbackManager(AbstractBaseManager):
    """
    Abstract base manager for postback models.
    
    Provides common manager functionality for postback
    related models.
    """
    
    @abstractmethod
    def get_by_network(self, network_key: str):
        """
        Get records by network key.
        
        Args:
            network_key: Network identifier
            
        Returns:
            QuerySet of records for the network
        """
        pass
    
    @abstractmethod
    def get_by_status(self, status: str):
        """
        Get records by status.
        
        Args:
            status: Status to filter by
            
        Returns:
            QuerySet of records with the status
        """
        pass
    
    @abstractmethod
    def get_recent(self, days: int = 7):
        """
        Get recent records.
        
        Args:
            days: Number of days to look back
            
        Returns:
            QuerySet of recent records
        """
        pass


class AbstractAnalyticsManager(AbstractBaseManager):
    """
    Abstract base manager for analytics models.
    
    Provides common manager functionality for analytics
    related models.
    """
    
    @abstractmethod
    def get_by_period(self, period: str = 'daily'):
        """
        Get records by time period.
        
        Args:
            period: Time period grouping
            
        Returns:
            QuerySet grouped by period
        """
        pass
    
    @abstractmethod
    def get_aggregated_metrics(self, metric_type: str) -> Dict[str, Any]:
        """
        Get aggregated metrics.
        
        Args:
            metric_type: Type of metric to aggregate
            
        Returns:
            Aggregated metrics data
        """
        pass
    
    @abstractmethod
    def get_trend_analysis(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get trend analysis data.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            List of trend data points
        """
        pass


class AbstractBaseView(ABC):
    """
    Abstract base view class.
    
    Provides common interface and functionality that all
    postback views should implement.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def get(self, request, *args, **kwargs):
        """
        Handle GET request.
        
        Args:
            request: HTTP request object
            *args: Additional arguments
            **kwargs: Additional keyword arguments
            
        Returns:
            HTTP response
        """
        pass
    
    @abstractmethod
    def post(self, request, *args, **kwargs):
        """
        Handle POST request.
        
        Args:
            request: HTTP request object
            *args: Additional arguments
            **kwargs: Additional keyword arguments
            
        Returns:
            HTTP response
        """
        pass
    
    @abstractmethod
    def validate_request_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate request data.
        
        Args:
            data: Request data to validate
            
        Returns:
            True if data is valid
        """
        pass
    
    def log_request(self, request: Any, message: str = None):
        """Log request information."""
        log_data = {
            'view': self.__class__.__name__,
            'method': request.method,
            'path': request.path,
            'timestamp': timezone.now().isoformat(),
        }
        
        self.logger.info(f"Request: {message or 'Request processed'} - {log_data}")
    
    def format_response(self, data: Any, status: int = 200) -> Dict[str, Any]:
        """Format response data."""
        return {
            'status': status,
            'data': data,
            'timestamp': timezone.now().isoformat(),
        }


class AbstractPostbackView(AbstractBaseView):
    """
    Abstract base view for postback-related views.
    
    Provides common interface for views that handle
    postback processing and management.
    """
    
    @abstractmethod
    def process_postback(self, request, postback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process postback data.
        
        Args:
            request: HTTP request object
            postback_data: Postback data to process
            
        Returns:
            Processing result
        """
        pass
    
    @abstractmethod
    def validate_postback_data(self, postback_data: Dict[str, Any]) -> bool:
        """
        Validate postback data.
        
        Args:
            postback_data: Postback data to validate
            
        Returns:
            True if data is valid
        """
        pass


class AbstractAnalyticsView(AbstractBaseView):
    """
    Abstract base view for analytics views.
    
    Provides common interface for views that handle
    analytics and reporting functionality.
    """
    
    @abstractmethod
    def generate_report(self, request, report_type: str) -> Dict[str, Any]:
        """
        Generate analytics report.
        
        Args:
            request: HTTP request object
            report_type: Type of report to generate
            
        Returns:
            Generated report data
        """
        pass
    
    @abstractmethod
    def get_metrics(self, request, metric_type: str) -> Dict[str, Any]:
        """
        Get analytics metrics.
        
        Args:
            request: HTTP request object
            metric_type: Type of metrics to retrieve
            
        Returns:
            Metrics data
        """
        pass


class AbstractBaseProcessor(ABC):
    """
    Abstract base processor class.
    
    Provides common interface for data processors
    in the postback system.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.processing_count = 0
        self.success_count = 0
        self.error_count = 0
    
    @abstractmethod
    def process(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process data.
        
        Args:
            data: Data to process
            context: Processing context
            
        Returns:
            Processing result
        """
        pass
    
    @abstractmethod
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """
        Validate input data.
        
        Args:
            data: Input data to validate
            
        Returns:
            True if data is valid
        """
        pass
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processor statistics."""
        success_rate = (self.success_count / self.processing_count * 100) if self.processing_count > 0 else 0
        
        return {
            'processor': self.__class__.__name__,
            'processing_count': self.processing_count,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'success_rate': f"{success_rate:.2f}%",
        }
    
    def update_statistics(self, success: bool):
        """Update processing statistics."""
        self.processing_count += 1
        
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
