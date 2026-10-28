# =============================================================================
# auto_mod/abstracts.py
# =============================================================================

"""
Abstract base classes for auto moderation system.
Provides base implementations for common patterns and interfaces.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from django.utils import timezone
from django.db import models

from .models import SuspiciousSubmission, ModerationDecision
from .exceptions import ModerationError

logger = logging.getLogger(__name__)


class BaseModerator(ABC):
    """Abstract base class for moderators."""
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
        self.is_active = True
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'avg_processing_time': 0.0,
        }
    
    @abstractmethod
    def moderate(self, submission: SuspiciousSubmission) -> Dict[str, Any]:
        """
        Moderate a submission.
        
        Args:
            submission: Submission to moderate
            
        Returns:
            Moderation result
        """
        pass
    
    @abstractmethod
    def can_handle(self, submission: SuspiciousSubmission) -> bool:
        """
        Check if moderator can handle the submission.
        
        Args:
            submission: Submission to check
            
        Returns:
            True if can handle
        """
        pass
    
    def update_stats(self, success: bool, processing_time: float) -> None:
        """Update moderation statistics."""
        self.stats['total_processed'] += 1
        
        if success:
            self.stats['successful'] += 1
        else:
            self.stats['failed'] += 1
        
        # Update average processing time
        total_time = self.stats['avg_processing_time'] * (self.stats['total_processed'] - 1)
        self.stats['avg_processing_time'] = (total_time + processing_time) / self.stats['total_processed']
    
    def get_stats(self) -> Dict[str, Any]:
        """Get moderator statistics."""
        return self.stats.copy()


class BaseScanner(ABC):
    """Abstract base class for content scanners."""
    
    def __init__(self, name: str, scanner_type: str, config: Dict[str, Any] = None):
        self.name = name
        self.scanner_type = scanner_type
        self.config = config or {}
        self.is_active = True
        self.supported_types = []
    
    @abstractmethod
    def scan(self, content: str, content_type: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Scan content for issues.
        
        Args:
            content: Content to scan
            content_type: Type of content
            metadata: Additional metadata
            
        Returns:
            Scan results
        """
        pass
    
    @abstractmethod
    def is_supported(self, content_type: str) -> bool:
        """
        Check if content type is supported.
        
        Args:
            content_type: Content type to check
            
        Returns:
            True if supported
        """
        pass
    
    def get_confidence_threshold(self) -> float:
        """Get confidence threshold for this scanner."""
        return self.config.get('confidence_threshold', 0.7)


class BaseAnalyzer(ABC):
    """Abstract base class for content analyzers."""
    
    def __init__(self, name: str, analyzer_type: str, config: Dict[str, Any] = None):
        self.name = name
        self.analyzer_type = analyzer_type
        self.config = config or {}
        self.is_active = True
    
    @abstractmethod
    def analyze(self, data: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze data.
        
        Args:
            data: Data to analyze
            context: Analysis context
            
        Returns:
            Analysis results
        """
        pass
    
    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """Get analyzer metrics."""
        pass


class BaseFilter(ABC):
    """Abstract base class for content filters."""
    
    def __init__(self, name: str, filter_type: str, config: Dict[str, Any] = None):
        self.name = name
        self.filter_type = filter_type
        self.config = config or {}
        self.is_active = True
    
    @abstractmethod
    def filter(self, item: Any, context: Dict[str, Any] = None) -> bool:
        """
        Filter item.
        
        Args:
            item: Item to filter
            context: Filter context
            
        Returns:
            True if item passes filter
        """
        pass
    
    @abstractmethod
    def get_filter_criteria(self) -> Dict[str, Any]:
        """Get filter criteria."""
        pass


class BaseNotifier(ABC):
    """Abstract base class for notification systems."""
    
    def __init__(self, name: str, notifier_type: str, config: Dict[str, Any] = None):
        self.name = name
        self.notifier_type = notifier_type
        self.config = config or {}
        self.is_active = True
    
    @abstractmethod
    def send_notification(self, recipients: List[str], message: str, 
                        metadata: Dict[str, Any] = None) -> bool:
        """
        Send notification.
        
        Args:
            recipients: List of recipient identifiers
            message: Notification message
            metadata: Additional metadata
            
        Returns:
            True if sent successfully
        """
        pass
    
    @abstractmethod
    def get_delivery_status(self, notification_id: str) -> Dict[str, Any]:
        """
        Get notification delivery status.
        
        Args:
            notification_id: Notification identifier
            
        Returns:
            Delivery status
        """
        pass


class BaseReporter(ABC):
    """Abstract base class for reporting systems."""
    
    def __init__(self, name: str, reporter_type: str, config: Dict[str, Any] = None):
        self.name = name
        self.reporter_type = reporter_type
        self.config = config or {}
        self.is_active = True
    
    @abstractmethod
    def generate_report(self, report_type: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate report.
        
        Args:
            report_type: Type of report
            parameters: Report parameters
            
        Returns:
            Report data
        """
        pass
    
    @abstractmethod
    def get_available_reports(self) -> List[str]:
        """Get list of available report types."""
        pass


class BaseValidator(ABC):
    """Abstract base class for validators."""
    
    def __init__(self, name: str, validator_type: str, config: Dict[str, Any] = None):
        self.name = name
        self.validator_type = validator_type
        self.config = config or {}
        self.is_active = True
    
    @abstractmethod
    def validate(self, data: Any, rules: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate data.
        
        Args:
            data: Data to validate
            rules: Validation rules
            
        Returns:
            Validation result
        """
        pass
    
    @abstractmethod
    def get_validation_rules(self) -> Dict[str, Any]:
        """Get validation rules."""
        pass


class BaseProcessor(ABC):
    """Abstract base class for data processors."""
    
    def __init__(self, name: str, processor_type: str, config: Dict[str, Any] = None):
        self.name = name
        self.processor_type = processor_type
        self.config = config or {}
        self.is_active = True
    
    @abstractmethod
    def process(self, data: Any, context: Dict[str, Any] = None) -> Any:
        """
        Process data.
        
        Args:
            data: Data to process
            context: Processing context
            
        Returns:
            Processed data
        """
        pass
    
    @abstractmethod
    def can_process(self, data: Any) -> bool:
        """
        Check if processor can handle the data.
        
        Args:
            data: Data to check
            
        Returns:
            True if can process
        """
        pass


class BaseTransformer(ABC):
    """Abstract base class for data transformers."""
    
    def __init__(self, name: str, transformer_type: str, config: Dict[str, Any] = None):
        self.name = name
        self.transformer_type = transformer_type
        self.config = config or {}
        self.is_active = True
    
    @abstractmethod
    def transform(self, data: Any, transformation_config: Dict[str, Any] = None) -> Any:
        """
        Transform data.
        
        Args:
            data: Data to transform
            transformation_config: Transformation configuration
            
        Returns:
            Transformed data
        """
        pass
    
    @abstractmethod
    def get_transformation_rules(self) -> Dict[str, Any]:
        """Get transformation rules."""
        pass


class BaseEnricher(ABC):
    """Abstract base class for data enrichers."""
    
    def __init__(self, name: str, enricher_type: str, config: Dict[str, Any] = None):
        self.name = name
        self.enricher_type = enricher_type
        self.config = config or {}
        self.is_active = True
    
    @abstractmethod
    def enrich(self, data: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Enrich data with additional information.
        
        Args:
            data: Data to enrich
            context: Enrichment context
            
        Returns:
            Enrichment data
        """
        pass
    
    @abstractmethod
    def get_enrichment_fields(self) -> List[str]:
        """Get list of enrichment fields."""
        pass


class BaseRuleEngine(ABC):
    """Abstract base class for rule engines."""
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
        self.is_active = True
        self.rules = []
    
    @abstractmethod
    def add_rule(self, rule: Any) -> bool:
        """
        Add a rule to the engine.
        
        Args:
            rule: Rule to add
            
        Returns:
            True if added successfully
        """
        pass
    
    @abstractmethod
    def remove_rule(self, rule_id: str) -> bool:
        """
        Remove a rule from the engine.
        
        Args:
            rule_id: ID of rule to remove
            
        Returns:
            True if removed successfully
        """
        pass
    
    @abstractmethod
    def evaluate_rules(self, data: Any, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Evaluate all rules against data.
        
        Args:
            data: Data to evaluate
            context: Evaluation context
            
        Returns:
            List of rule evaluation results
        """
        pass


class BaseWorkflow(ABC):
    """Abstract base class for workflows."""
    
    def __init__(self, name: str, workflow_type: str, config: Dict[str, Any] = None):
        self.name = name
        self.workflow_type = workflow_type
        self.config = config or {}
        self.is_active = True
        self.steps = []
    
    @abstractmethod
    def add_step(self, step: Any) -> bool:
        """
        Add a step to the workflow.
        
        Args:
            step: Step to add
            
        Returns:
            True if added successfully
        """
        pass
    
    @abstractmethod
    def execute(self, data: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute the workflow.
        
        Args:
            data: Input data
            context: Execution context
            
        Returns:
            Workflow execution result
        """
        pass
    
    @abstractmethod
    def get_workflow_status(self) -> Dict[str, Any]:
        """Get workflow status."""
        pass


class BaseAdapter(ABC):
    """Abstract base class for adapters."""
    
    def __init__(self, name: str, adapter_type: str, config: Dict[str, Any] = None):
        self.name = name
        self.adapter_type = adapter_type
        self.config = config or {}
        self.is_active = True
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection.
        
        Returns:
            True if connected successfully
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """
        Close connection.
        
        Returns:
            True if disconnected successfully
        """
        pass
    
    @abstractmethod
    def send(self, data: Any) -> Any:
        """
        Send data through adapter.
        
        Args:
            data: Data to send
            
        Returns:
            Response data
        """
        pass
    
    @abstractmethod
    def receive(self) -> Any:
        """
        Receive data through adapter.
        
        Returns:
            Received data
        """
        pass


class BaseEventHandler(ABC):
    """Abstract base class for event handlers."""
    
    def __init__(self, name: str, event_type: str, config: Dict[str, Any] = None):
        self.name = name
        self.event_type = event_type
        self.config = config or {}
        self.is_active = True
    
    @abstractmethod
    def handle_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle event.
        
        Args:
            event_data: Event data
            
        Returns:
            Handler response
        """
        pass
    
    @abstractmethod
    def can_handle(self, event_type: str) -> bool:
        """
        Check if handler can handle event type.
        
        Args:
            event_type: Event type to check
            
        Returns:
            True if can handle
        """
        pass


class BaseScheduler(ABC):
    """Abstract base class for schedulers."""
    
    def __init__(self, name: str, scheduler_type: str, config: Dict[str, Any] = None):
        self.name = name
        self.scheduler_type = scheduler_type
        self.config = config or {}
        self.is_active = True
        self.jobs = []
    
    @abstractmethod
    def schedule_job(self, job: Any, schedule: str) -> bool:
        """
        Schedule a job.
        
        Args:
            job: Job to schedule
            schedule: Schedule expression
            
        Returns:
            True if scheduled successfully
        """
        pass
    
    @abstractmethod
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a scheduled job.
        
        Args:
            job_id: ID of job to cancel
            
        Returns:
            True if cancelled successfully
        """
        pass
    
    @abstractmethod
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get job status.
        
        Args:
            job_id: ID of job
            
        Returns:
            Job status
        """
        pass


class BaseRepository(ABC):
    """Abstract base class for repositories."""
    
    def __init__(self, name: str, repository_type: str, config: Dict[str, Any] = None):
        self.name = name
        self.repository_type = repository_type
        self.config = config or {}
        self.is_active = True
    
    @abstractmethod
    def create(self, data: Dict[str, Any]) -> Any:
        """
        Create a new record.
        
        Args:
            data: Data to create
            
        Returns:
            Created record
        """
        pass
    
    @abstractmethod
    def get(self, id: str) -> Any:
        """
        Get a record by ID.
        
        Args:
            id: Record ID
            
        Returns:
            Record data
        """
        pass
    
    @abstractmethod
    def update(self, id: str, data: Dict[str, Any]) -> Any:
        """
        Update a record.
        
        Args:
            id: Record ID
            data: Update data
            
        Returns:
            Updated record
        """
        pass
    
    @abstractmethod
    def delete(self, id: str) -> bool:
        """
        Delete a record.
        
        Args:
            id: Record ID
            
        Returns:
            True if deleted successfully
        """
        pass
    
    @abstractmethod
    def list(self, filters: Dict[str, Any] = None, limit: int = None) -> List[Any]:
        """
        List records.
        
        Args:
            filters: Filter criteria
            limit: Maximum number of records
            
        Returns:
            List of records
        """
        pass


class BaseService(ABC):
    """Abstract base class for services."""
    
    def __init__(self, name: str, service_type: str, config: Dict[str, Any] = None):
        self.name = name
        self.service_type = service_type
        self.config = config or {}
        self.is_active = True
    
    @abstractmethod
    def start(self) -> bool:
        """
        Start the service.
        
        Returns:
            True if started successfully
        """
        pass
    
    @abstractmethod
    def stop(self) -> bool:
        """
        Stop the service.
        
        Returns:
            True if stopped successfully
        """
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        Get service status.
        
        Returns:
            Service status
        """
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check.
        
        Returns:
            Health check results
        """
        pass


# Abstract model base classes
class AbstractModerationModel(models.Model):
    """Abstract base model for moderation."""
    
    class Meta:
        abstract = True
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        """Override save to add validation."""
        self.full_clean()
        super().save(*args, **kwargs)


class AbstractTimestampedModel(models.Model):
    """Abstract model with timestamps."""
    
    class Meta:
        abstract = True
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class AbstractSoftDeleteModel(models.Model):
    """Abstract model with soft delete."""
    
    class Meta:
        abstract = True
    
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    def soft_delete(self):
        """Soft delete the instance."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore the soft deleted instance."""
        self.is_deleted = False
        self.deleted_at = None
        self.save()


class AbstractUUIDModel(models.Model):
    """Abstract model with UUID primary key."""
    
    class Meta:
        abstract = True
    
    id = models.UUIDField(primary_key=True, editable=False)


# Initialize logging
logger.info("Abstracts module initialized with base class definitions")
