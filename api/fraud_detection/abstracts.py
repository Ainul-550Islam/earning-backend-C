# =============================================================================
# fraud_detection/abstracts.py
# =============================================================================
"""
Abstract Base Classes for Fraud Detection System.

Provides abstract base classes and interfaces for fraud detection
components, ensuring consistent architecture and implementation patterns.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Type
from dataclasses import dataclass
from enum import Enum

from django.utils import timezone
from django.db import models

from api.fraud_detection.exceptions import FraudDetectionError


logger = logging.getLogger(__name__)


class DetectionStrategy(Enum):
    """Fraud detection strategies."""
    RULE_BASED = "rule_based"
    MACHINE_LEARNING = "machine_learning"
    HYBRID = "hybrid"
    BEHAVIORAL = "behavioral"
    STATISTICAL = "statistical"
    REAL_TIME = "real_time"
    BATCH = "batch"


class RiskLevel(Enum):
    """Risk levels."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    CRITICAL = "critical"


@dataclass
class DetectionContext:
    """Context for fraud detection operations."""
    user_id: Union[int, str]
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()


@dataclass
class DetectionResult:
    """Result of fraud detection operation."""
    fraud_detected: bool
    risk_score: int
    risk_level: RiskLevel
    confidence_score: float
    indicators: List[str]
    recommendations: List[str]
    processing_time_ms: float
    detection_method: DetectionStrategy
    context: DetectionContext
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseFraudDetector(ABC):
    """Abstract base class for fraud detectors."""
    
    def __init__(self, name: str, strategy: DetectionStrategy):
        """Initialize detector."""
        self.name = name
        self.strategy = strategy
        self.enabled = True
        self.last_execution = None
        self.execution_count = 0
        self.error_count = 0
    
    @abstractmethod
    def detect(self, context: DetectionContext, data: Dict[str, Any]) -> DetectionResult:
        """
        Detect fraud in provided data.
        
        Args:
            context: Detection context
            data: Data to analyze
            
        Returns:
            Detection result
        """
        pass
    
    @abstractmethod
    def train(self, training_data: List[Dict[str, Any]]) -> bool:
        """
        Train the detector with provided data.
        
        Args:
            training_data: Training data
            
        Returns:
            True if training successful
        """
        pass
    
    @abstractmethod
    def validate_configuration(self) -> bool:
        """
        Validate detector configuration.
        
        Returns:
            True if configuration is valid
        """
        pass
    
    def execute(self, context: DetectionContext, data: Dict[str, Any]) -> DetectionResult:
        """
        Execute fraud detection with error handling.
        
        Args:
            context: Detection context
            data: Data to analyze
            
        Returns:
            Detection result
        """
        if not self.enabled:
            raise FraudDetectionError(f"Detector {self.name} is disabled")
        
        start_time = timezone.now()
        
        try:
            self.execution_count += 1
            self.last_execution = start_time
            
            result = self.detect(context, data)
            result.processing_time_ms = (timezone.now() - start_time).total_seconds() * 1000
            
            return result
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Detector {self.name} execution failed: {e}")
            raise FraudDetectionError(f"Detection failed: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get detector statistics."""
        return {
            'name': self.name,
            'strategy': self.strategy.value,
            'enabled': self.enabled,
            'execution_count': self.execution_count,
            'error_count': self.error_count,
            'last_execution': self.last_execution.isoformat() if self.last_execution else None,
            'error_rate': self.error_count / max(self.execution_count, 1)
        }


class BaseRiskAssessor(ABC):
    """Abstract base class for risk assessors."""
    
    def __init__(self, name: str):
        """Initialize risk assessor."""
        self.name = name
        self.enabled = True
        self.risk_factors = {}
        self.weights = {}
    
    @abstractmethod
    def assess_risk(self, context: DetectionContext, 
                    historical_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Assess risk for provided context.
        
        Args:
            context: Detection context
            historical_data: Historical user data
            
        Returns:
            Risk assessment result
        """
        pass
    
    @abstractmethod
    def calculate_risk_score(self, factors: Dict[str, Any]) -> int:
        """
        Calculate risk score from factors.
        
        Args:
            factors: Risk factors
            
        Returns:
            Risk score (0-100)
        """
        pass
    
    @abstractmethod
    def get_risk_level(self, risk_score: int) -> RiskLevel:
        """
        Get risk level from score.
        
        Args:
            risk_score: Risk score
            
        Returns:
            Risk level
        """
        pass
    
    def update_weights(self, new_weights: Dict[str, float]):
        """Update risk factor weights."""
        self.weights.update(new_weights)
    
    def add_risk_factor(self, factor_name: str, weight: float):
        """Add risk factor."""
        self.risk_factors[factor_name] = weight
        self.weights[factor_name] = weight


class BaseDataProvider(ABC):
    """Abstract base class for data providers."""
    
    def __init__(self, name: str, data_type: str):
        """Initialize data provider."""
        self.name = name
        self.data_type = data_type
        self.cache_enabled = True
        self.cache_timeout = 300  # 5 minutes
    
    @abstractmethod
    def fetch_data(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch data based on query.
        
        Args:
            query: Data query
            
        Returns:
            Fetched data
        """
        pass
    
    @abstractmethod
    def validate_query(self, query: Dict[str, Any]) -> bool:
        """
        Validate data query.
        
        Args:
            query: Query to validate
            
        Returns:
            True if query is valid
        """
        pass
    
    @abstractmethod
    def get_data_schema(self) -> Dict[str, Any]:
        """
        Get data schema.
        
        Returns:
            Data schema definition
        """
        pass


class BaseNotificationSender(ABC):
    """Abstract base class for notification senders."""
    
    def __init__(self, name: str, channel: str):
        """Initialize notification sender."""
        self.name = name
        self.channel = channel
        self.enabled = True
        self.rate_limit = None
    
    @abstractmethod
    def send_notification(self, recipient: str, message: str, 
                         metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send notification to recipient.
        
        Args:
            recipient: Notification recipient
            message: Notification message
            metadata: Additional metadata
            
        Returns:
            True if sent successfully
        """
        pass
    
    @abstractmethod
    def validate_recipient(self, recipient: str) -> bool:
        """
        Validate notification recipient.
        
        Args:
            recipient: Recipient to validate
            
        Returns:
            True if recipient is valid
        """
        pass
    
    @abstractmethod
    def format_message(self, message: str, template_data: Dict[str, Any]) -> str:
        """
        Format message with template data.
        
        Args:
            message: Message template
            template_data: Template data
            
        Returns:
            Formatted message
        """
        pass


class BaseAnalyticsProcessor(ABC):
    """Abstract base class for analytics processors."""
    
    def __init__(self, name: str, analysis_type: str):
        """Initialize analytics processor."""
        self.name = name
        self.analysis_type = analysis_type
        self.cache_results = True
    
    @abstractmethod
    def process_analytics(self, data: List[Dict[str, Any]], 
                          parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process analytics on provided data.
        
        Args:
            data: Data to analyze
            parameters: Analysis parameters
            
        Returns:
            Analytics results
        """
        pass
    
    @abstractmethod
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """
        Validate analysis parameters.
        
        Args:
            parameters: Parameters to validate
            
        Returns:
            True if parameters are valid
        """
        pass
    
    @abstractmethod
    def get_required_fields(self) -> List[str]:
        """
        Get required data fields for analysis.
        
        Returns:
            List of required field names
        """
        pass


class BaseRuleEngine(ABC):
    """Abstract base class for rule engines."""
    
    def __init__(self, name: str):
        """Initialize rule engine."""
        self.name = name
        self.rules = {}
        self.rule_execution_order = []
    
    @abstractmethod
    def add_rule(self, rule_name: str, rule_definition: Dict[str, Any]) -> bool:
        """
        Add rule to engine.
        
        Args:
            rule_name: Rule name
            rule_definition: Rule definition
            
        Returns:
            True if rule added successfully
        """
        pass
    
    @abstractmethod
    def remove_rule(self, rule_name: str) -> bool:
        """
        Remove rule from engine.
        
        Args:
            rule_name: Rule name
            
        Returns:
            True if rule removed successfully
        """
        pass
    
    @abstractmethod
    def evaluate_rules(self, context: DetectionContext, 
                       data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluate all rules against data.
        
        Args:
            context: Detection context
            data: Data to evaluate
            
        Returns:
            List of rule evaluation results
        """
        pass
    
    @abstractmethod
    def validate_rule(self, rule_definition: Dict[str, Any]) -> bool:
        """
        Validate rule definition.
        
        Args:
            rule_definition: Rule definition
            
        Returns:
            True if rule is valid
        """
        pass


class BaseModelManager(ABC):
    """Abstract base class for model managers."""
    
    def __init__(self, model_class: Type[models.Model]):
        """Initialize model manager."""
        self.model_class = model_class
        self.queryset = model_class.objects.all()
    
    @abstractmethod
    def get_by_id(self, instance_id: Union[int, str]) -> Optional[models.Model]:
        """
        Get model instance by ID.
        
        Args:
            instance_id: Instance ID
            
        Returns:
            Model instance or None
        """
        pass
    
    @abstractmethod
    def create(self, **kwargs) -> models.Model:
        """
        Create new model instance.
        
        Args:
            **kwargs: Instance data
            
        Returns:
            Created instance
        """
        pass
    
    @abstractmethod
    def update(self, instance_id: Union[int, str], **kwargs) -> Optional[models.Model]:
        """
        Update model instance.
        
        Args:
            instance_id: Instance ID
            **kwargs: Update data
            
        Returns:
            Updated instance or None
        """
        pass
    
    @abstractmethod
    def delete(self, instance_id: Union[int, str]) -> bool:
        """
        Delete model instance.
        
        Args:
            instance_id: Instance ID
            
        Returns:
            True if deleted successfully
        """
        pass
    
    @abstractmethod
    def filter_by_criteria(self, criteria: Dict[str, Any]) -> models.QuerySet:
        """
        Filter instances by criteria.
        
        Args:
            criteria: Filter criteria
            
        Returns:
            Filtered queryset
        """
        pass


class BaseRepository(ABC):
    """Abstract base class for repositories."""
    
    def __init__(self, model_manager: BaseModelManager):
        """Initialize repository."""
        self.model_manager = model_manager
    
    @abstractmethod
    def find_by_id(self, entity_id: Union[int, str]) -> Optional[Any]:
        """
        Find entity by ID.
        
        Args:
            entity_id: Entity ID
            
        Returns:
            Entity or None
        """
        pass
    
    @abstractmethod
    def find_by_criteria(self, criteria: Dict[str, Any]) -> List[Any]:
        """
        Find entities by criteria.
        
        Args:
            criteria: Search criteria
            
        Returns:
            List of entities
        """
        pass
    
    @abstractmethod
    def save(self, entity: Any) -> Any:
        """
        Save entity.
        
        Args:
            entity: Entity to save
            
        Returns:
            Saved entity
        """
        pass
    
    @abstractmethod
    def delete(self, entity_id: Union[int, str]) -> bool:
        """
        Delete entity by ID.
        
        Args:
            entity_id: Entity ID
            
        Returns:
            True if deleted successfully
        """
        pass
    
    @abstractmethod
    def count_by_criteria(self, criteria: Dict[str, Any]) -> int:
        """
        Count entities by criteria.
        
        Args:
            criteria: Count criteria
            
        Returns:
            Entity count
        """
        pass


class BaseService(ABC):
    """Abstract base class for services."""
    
    def __init__(self, name: str):
        """Initialize service."""
        self.name = name
        self.dependencies = {}
        self.enabled = True
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize service.
        
        Returns:
            True if initialization successful
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> bool:
        """
        Cleanup service resources.
        
        Returns:
            True if cleanup successful
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
    
    def add_dependency(self, dependency_name: str, dependency: Any):
        """Add service dependency."""
        self.dependencies[dependency_name] = dependency
    
    def get_dependency(self, dependency_name: str) -> Any:
        """Get service dependency."""
        return self.dependencies.get(dependency_name)


class BaseEventHandler(ABC):
    """Abstract base class for event handlers."""
    
    def __init__(self, name: str, event_types: List[str]):
        """Initialize event handler."""
        self.name = name
        self.event_types = event_types
        self.enabled = True
    
    @abstractmethod
    def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """
        Handle event.
        
        Args:
            event_type: Type of event
            event_data: Event data
            
        Returns:
            True if handled successfully
        """
        pass
    
    @abstractmethod
    def can_handle_event(self, event_type: str) -> bool:
        """
        Check if handler can handle event type.
        
        Args:
            event_type: Event type
            
        Returns:
            True if can handle
        """
        pass
    
    def process_event(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """
        Process event with error handling.
        
        Args:
            event_type: Event type
            event_data: Event data
            
        Returns:
            True if processed successfully
        """
        if not self.enabled:
            return False
        
        if not self.can_handle_event(event_type):
            return False
        
        try:
            return self.handle_event(event_type, event_data)
        except Exception as e:
            logger.error(f"Event handler {self.name} failed: {e}")
            return False


class BaseValidator(ABC):
    """Abstract base class for validators."""
    
    def __init__(self, name: str):
        """Initialize validator."""
        self.name = name
        self.validation_rules = {}
    
    @abstractmethod
    def validate(self, data: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate data.
        
        Args:
            data: Data to validate
            context: Validation context
            
        Returns:
            Validation results
        """
        pass
    
    @abstractmethod
    def add_validation_rule(self, rule_name: str, rule_func: callable):
        """
        Add validation rule.
        
        Args:
            rule_name: Rule name
            rule_func: Validation function
        """
        pass
    
    @abstractmethod
    def remove_validation_rule(self, rule_name: str) -> bool:
        """
        Remove validation rule.
        
        Args:
            rule_name: Rule name
            
        Returns:
            True if removed successfully
        """
        pass


class BaseTransformer(ABC):
    """Abstract base class for data transformers."""
    
    def __init__(self, name: str, input_type: str, output_type: str):
        """Initialize transformer."""
        self.name = name
        self.input_type = input_type
        self.output_type = output_type
    
    @abstractmethod
    def transform(self, data: Any, parameters: Optional[Dict[str, Any]] = None) -> Any:
        """
        Transform data.
        
        Args:
            data: Data to transform
            parameters: Transformation parameters
            
        Returns:
            Transformed data
        """
        pass
    
    @abstractmethod
    def validate_input(self, data: Any) -> bool:
        """
        Validate input data.
        
        Args:
            data: Input data
            
        Returns:
            True if input is valid
        """
        pass
    
    @abstractmethod
    def validate_output(self, data: Any) -> bool:
        """
        Validate output data.
        
        Args:
            data: Output data
            
        Returns:
            True if output is valid
        """
        pass


class BaseExporter(ABC):
    """Abstract base class for data exporters."""
    
    def __init__(self, name: str, export_format: str):
        """Initialize exporter."""
        self.name = name
        self.export_format = export_format
        self.supported_formats = []
    
    @abstractmethod
    def export(self, data: List[Dict[str, Any]], 
               options: Optional[Dict[str, Any]] = None) -> bytes:
        """
        Export data to specified format.
        
        Args:
            data: Data to export
            options: Export options
            
        Returns:
            Exported data as bytes
        """
        pass
    
    @abstractmethod
    def get_file_extension(self) -> str:
        """
        Get file extension for export format.
        
        Returns:
            File extension
        """
        pass
    
    @abstractmethod
    def validate_export_options(self, options: Dict[str, Any]) -> bool:
        """
        Validate export options.
        
        Args:
            options: Export options
            
        Returns:
            True if options are valid
        """
        pass


class BaseIntegrator(ABC):
    """Abstract base class for system integrators."""
    
    def __init__(self, name: str, target_system: str):
        """Initialize integrator."""
        self.name = name
        self.target_system = target_system
        self.connection_config = {}
        self.is_connected = False
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to target system.
        
        Returns:
            True if connected successfully
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """
        Disconnect from target system.
        
        Returns:
            True if disconnected successfully
        """
        pass
    
    @abstractmethod
    def send_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send data to target system.
        
        Args:
            data: Data to send
            
        Returns:
            Response from target system
        """
        pass
    
    @abstractmethod
    def receive_data(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receive data from target system.
        
        Args:
            query: Data query
            
        Returns:
            Received data
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test connection to target system.
        
        Returns:
            True if connection is working
        """
        pass


# Abstract factory classes
class AbstractDetectorFactory(ABC):
    """Abstract factory for creating detectors."""
    
    @abstractmethod
    def create_detector(self, detector_type: str, **kwargs) -> BaseFraudDetector:
        """
        Create detector instance.
        
        Args:
            detector_type: Type of detector
            **kwargs: Detector configuration
            
        Returns:
            Detector instance
        """
        pass
    
    @abstractmethod
    def get_supported_types(self) -> List[str]:
        """
        Get supported detector types.
        
        Returns:
            List of supported types
        """
        pass


class AbstractServiceFactory(ABC):
    """Abstract factory for creating services."""
    
    @abstractmethod
    def create_service(self, service_type: str, **kwargs) -> BaseService:
        """
        Create service instance.
        
        Args:
            service_type: Type of service
            **kwargs: Service configuration
            
        Returns:
            Service instance
        """
        pass
    
    @abstractmethod
    def get_supported_services(self) -> List[str]:
        """
        Get supported service types.
        
        Returns:
            List of supported types
        """
        pass


# Abstract interfaces
class IFraudDetectionSystem(ABC):
    """Interface for fraud detection system."""
    
    @abstractmethod
    def detect_fraud(self, context: DetectionContext, 
                     transaction_data: Dict[str, Any]) -> DetectionResult:
        """Detect fraud in transaction data."""
        pass
    
    @abstractmethod
    def assess_risk(self, user_id: Union[int, str], 
                   context: DetectionContext) -> Dict[str, Any]:
        """Assess user risk."""
        pass
    
    @abstractmethod
    def create_case(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create fraud case."""
        pass
    
    @abstractmethod
    def generate_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fraud alert."""
        pass


class IComplianceSystem(ABC):
    """Interface for compliance system."""
    
    @abstractmethod
    def check_compliance(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check compliance requirements."""
        pass
    
    @abstractmethod
    def generate_report(self, report_type: str, 
                       parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate compliance report."""
        pass
    
    @abstractmethod
    def file_regulatory_report(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """File regulatory report."""
        pass


class IAnalyticsSystem(ABC):
    """Interface for analytics system."""
    
    @abstractmethod
    def generate_overview(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fraud overview analytics."""
        pass
    
    @abstractmethod
    def analyze_trends(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze fraud trends."""
        pass
    
    @abstractmethod
    def calculate_metrics(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate fraud metrics."""
        pass


# Export all abstract classes
__all__ = [
    # Enums and data classes
    'DetectionStrategy',
    'RiskLevel',
    'DetectionContext',
    'DetectionResult',
    
    # Abstract base classes
    'BaseFraudDetector',
    'BaseRiskAssessor',
    'BaseDataProvider',
    'BaseNotificationSender',
    'BaseAnalyticsProcessor',
    'BaseRuleEngine',
    'BaseModelManager',
    'BaseRepository',
    'BaseService',
    'BaseEventHandler',
    'BaseValidator',
    'BaseTransformer',
    'BaseExporter',
    'BaseIntegrator',
    
    # Abstract factories
    'AbstractDetectorFactory',
    'AbstractServiceFactory',
    
    # Interfaces
    'IFraudDetectionSystem',
    'IComplianceSystem',
    'IAnalyticsSystem',
]
