"""
Security Abstracts Module
Abstract base classes for security components
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Type, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import models

from .utils import SecurityUtils

User = get_user_model()
logger = logging.getLogger('security.abstracts')


class SecurityModel(models.Model):
    """Abstract base model for security models"""
    
    id = models.UUIDField(primary_key=True, default=SecurityUtils.generate_uuid)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        abstract = True
    
    def __str__(self):
        return f"{self.__class__.__name__} - {self.id}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        result = {}
        for field in self._meta.fields:
            field_name = field.name
            field_value = getattr(self, field_name)
            
            if isinstance(field_value, datetime):
                result[field_name] = field_value.isoformat()
            elif isinstance(field_value, User):
                result[field_name] = field_value.username if field_value else None
            else:
                result[field_name] = field_value
        
        return result
    
    def get_metadata_value(self, key: str, default=None):
        """Get metadata value"""
        return self.metadata.get(key, default)
    
    def set_metadata_value(self, key: str, value):
        """Set metadata value"""
        self.metadata[key] = value
        self.save(update_fields=['metadata'])


class UserSecurityModel(SecurityModel):
    """Abstract base model for user-related security models"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')
    
    class Meta:
        abstract = True
    
    def __str__(self):
        return f"{self.__class__.__name__} - {self.user.username}"


class TenantSecurityModel(SecurityModel):
    """Abstract base model for tenant-related security models"""
    
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='+')
    
    class Meta:
        abstract = True
    
    def __str__(self):
        return f"{self.__class__.__name__} - {self.tenant.name}"


class AbstractSecurityService(ABC):
    """Abstract base class for security services"""
    
    def __init__(self, name: str):
        self.name = name
        self.config = {}
        self.initialized = False
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any] = None) -> bool:
        """Initialize the service"""
        pass
    
    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the service logic"""
        pass
    
    @abstractmethod
    def cleanup(self) -> bool:
        """Clean up service resources"""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status"""
        return {
            'name': self.name,
            'initialized': self.initialized,
            'config': self.config
        }


class SecurityValidator(ABC):
    """Abstract base class for security validators"""
    
    def __init__(self, validator_type: str):
        self.validator_type = validator_type
        self.config = {}
    
    @abstractmethod
    def validate(self, data: Any, rules: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate data"""
        pass
    
    @abstractmethod
    def get_validation_rules(self) -> Dict[str, Any]:
        """Get validation rules"""
        pass
    
    def set_config(self, config: Dict[str, Any]):
        """Set validator configuration"""
        self.config = config


class SecurityAnalyzer(ABC):
    """Abstract base class for security analyzers"""
    
    def __init__(self, analyzer_type: str):
        self.analyzer_type = analyzer_type
        self.config = {}
    
    @abstractmethod
    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze security data"""
        pass
    
    @abstractmethod
    def get_analysis_types(self) -> List[str]:
        """Get supported analysis types"""
        pass
    
    def set_config(self, config: Dict[str, Any]):
        """Set analyzer configuration"""
        self.config = config


class SecurityDetector(ABC):
    """Abstract base class for security detectors"""
    
    def __init__(self, detector_type: str):
        self.detector_type = detector_type
        self.config = {}
        self.enabled = True
    
    @abstractmethod
    def detect(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect security threats"""
        pass
    
    @abstractmethod
    def get_threat_types(self) -> List[str]:
        """Get supported threat types"""
        pass
    
    def enable(self):
        """Enable detector"""
        self.enabled = True
    
    def disable(self):
        """Disable detector"""
        self.enabled = False
    
    def set_config(self, config: Dict[str, Any]):
        """Set detector configuration"""
        self.config = config


class SecurityReporter(ABC):
    """Abstract base class for security reporters"""
    
    def __init__(self, reporter_type: str):
        self.reporter_type = reporter_type
        self.config = {}
    
    @abstractmethod
    def generate_report(self, report_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate security report"""
        pass
    
    @abstractmethod
    def get_report_types(self) -> List[str]:
        """Get supported report types"""
        pass
    
    def set_config(self, config: Dict[str, Any]):
        """Set reporter configuration"""
        self.config = config


class AbstractSecurityMonitor(ABC):
    """Abstract base class for security monitors"""
    
    def __init__(self, monitor_type: str):
        self.monitor_type = monitor_type
        self.config = {}
        self.active = False
    
    @abstractmethod
    def start_monitoring(self) -> bool:
        """Start monitoring"""
        pass
    
    @abstractmethod
    def stop_monitoring(self) -> bool:
        """Stop monitoring"""
        pass
    
    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """Get monitoring metrics"""
        pass
    
    def set_config(self, config: Dict[str, Any]):
        """Set monitor configuration"""
        self.config = config


class SecurityFilter(ABC):
    """Abstract base class for security filters"""
    
    def __init__(self, filter_type: str):
        self.filter_type = filter_type
        self.config = {}
    
    @abstractmethod
    def filter(self, data: List[Dict[str, Any]], criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Filter data based on criteria"""
        pass
    
    @abstractmethod
    def get_filter_options(self) -> Dict[str, Any]:
        """Get filter options"""
        pass
    
    def set_config(self, config: Dict[str, Any]):
        """Set filter configuration"""
        self.config = config


class SecurityProcessor(ABC):
    """Abstract base class for security processors"""
    
    def __init__(self, processor_type: str):
        self.processor_type = processor_type
        self.config = {}
    
    @abstractmethod
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process security data"""
        pass
    
    @abstractmethod
    def get_processing_types(self) -> List[str]:
        """Get supported processing types"""
        pass
    
    def set_config(self, config: Dict[str, Any]):
        """Set processor configuration"""
        self.config = config


class SecurityTransformer(ABC):
    """Abstract base class for security transformers"""
    
    def __init__(self, transformer_type: str):
        self.transformer_type = transformer_type
        self.config = {}
    
    @abstractmethod
    def transform(self, data: Dict[str, Any], target_format: str) -> Dict[str, Any]:
        """Transform data to target format"""
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """Get supported formats"""
        pass
    
    def set_config(self, config: Dict[str, Any]):
        """Set transformer configuration"""
        self.config = config


class SecurityRepository(ABC):
    """Abstract base class for security repositories"""
    
    def __init__(self, model_class: Type[models.Model]):
        self.model_class = model_class
        self.queryset = model_class.objects.all()
    
    @abstractmethod
    def create(self, data: Dict[str, Any]) -> models.Model:
        """Create new record"""
        pass
    
    @abstractmethod
    def get_by_id(self, id: str) -> Optional[models.Model]:
        """Get record by ID"""
        pass
    
    @abstractmethod
    def update(self, id: str, data: Dict[str, Any]) -> Optional[models.Model]:
        """Update record"""
        pass
    
    @abstractmethod
    def delete(self, id: str) -> bool:
        """Delete record"""
        pass
    
    @abstractmethod
    def list(self, filters: Dict[str, Any] = None) -> models.QuerySet:
        """List records with filters"""
        pass
    
    def get_queryset(self) -> models.QuerySet:
        """Get base queryset"""
        return self.queryset
    
    def set_queryset(self, queryset: models.QuerySet):
        """Set custom queryset"""
        self.queryset = queryset


class SecurityUseCase(ABC):
    """Abstract base class for security use cases"""
    
    def __init__(self, name: str):
        self.name = name
        self.repositories = {}
        self.services = {}
    
    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute use case"""
        pass
    
    @abstractmethod
    def validate_context(self, context: Dict[str, Any]) -> bool:
        """Validate execution context"""
        pass
    
    def add_repository(self, name: str, repository: SecurityRepository):
        """Add repository"""
        self.repositories[name] = repository
    
    def add_service(self, name: str, service: AbstractSecurityService):
        """Add service"""
        self.services[name] = service
    
    def get_repository(self, name: str) -> Optional[SecurityRepository]:
        """Get repository"""
        return self.repositories.get(name)
    
    def get_service(self, name: str) -> Optional[AbstractSecurityService]:
        """Get service"""
        return self.services.get(name)


class SecurityInteractor(ABC):
    """Abstract base class for security interactors"""
    
    def __init__(self, name: str):
        self.name = name
        self.use_cases = {}
    
    @abstractmethod
    def interact(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Interact with system"""
        pass
    
    @abstractmethod
    def validate_request(self, request_data: Dict[str, Any]) -> bool:
        """Validate request data"""
        pass
    
    def add_use_case(self, name: str, use_case: SecurityUseCase):
        """Add use case"""
        self.use_cases[name] = use_case
    
    def get_use_case(self, name: str) -> Optional[SecurityUseCase]:
        """Get use case"""
        return self.use_cases.get(name)


class SecurityEventHandler(ABC):
    """Abstract base class for security event handlers"""
    
    def __init__(self, event_type: str):
        self.event_type = event_type
        self.config = {}
        self.enabled = True
    
    @abstractmethod
    def handle(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle security event"""
        pass
    
    @abstractmethod
    def can_handle(self, event: Dict[str, Any]) -> bool:
        """Check if can handle event"""
        pass
    
    def enable(self):
        """Enable handler"""
        self.enabled = True
    
    def disable(self):
        """Disable handler"""
        self.enabled = False
    
    def set_config(self, config: Dict[str, Any]):
        """Set handler configuration"""
        self.config = config


class SecurityNotifier(ABC):
    """Abstract base class for security notifiers"""
    
    def __init__(self, notifier_type: str):
        self.notifier_type = notifier_type
        self.config = {}
        self.enabled = True
    
    @abstractmethod
    def notify(self, message: str, recipients: List[str], context: Dict[str, Any] = None) -> bool:
        """Send notification"""
        pass
    
    @abstractmethod
    def get_notification_types(self) -> List[str]:
        """Get supported notification types"""
        pass
    
    def enable(self):
        """Enable notifier"""
        self.enabled = True
    
    def disable(self):
        """Disable notifier"""
        self.enabled = False
    
    def set_config(self, config: Dict[str, Any]):
        """Set notifier configuration"""
        self.config = config


class SecurityAuditor(ABC):
    """Abstract base class for security auditors"""
    
    def __init__(self, auditor_type: str):
        self.auditor_type = auditor_type
        self.config = {}
    
    @abstractmethod
    def audit(self, target: str, criteria: Dict[str, Any] = None) -> Dict[str, Any]:
        """Perform security audit"""
        pass
    
    @abstractmethod
    def get_audit_types(self) -> List[str]:
        """Get supported audit types"""
        pass
    
    def set_config(self, config: Dict[str, Any]):
        """Set auditor configuration"""
        self.config = config


class AbstractSecurityPolicy(ABC):
    """Abstract base class for security policies"""
    
    def __init__(self, policy_name: str):
        self.policy_name = policy_name
        self.rules = {}
        self.enabled = True
    
    @abstractmethod
    def evaluate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate policy against context"""
        pass
    
    @abstractmethod
    def get_policy_rules(self) -> Dict[str, Any]:
        """Get policy rules"""
        pass
    
    def enable(self):
        """Enable policy"""
        self.enabled = True
    
    def disable(self):
        """Disable policy"""
        self.enabled = False
    
    def add_rule(self, rule_name: str, rule_config: Dict[str, Any]):
        """Add policy rule"""
        self.rules[rule_name] = rule_config
    
    def remove_rule(self, rule_name: str):
        """Remove policy rule"""
        if rule_name in self.rules:
            del self.rules[rule_name]


class SecurityEnforcer(ABC):
    """Abstract base class for security enforcers"""
    
    def __init__(self, enforcer_type: str):
        self.enforcer_type = enforcer_type
        self.config = {}
        self.policies = {}
    
    @abstractmethod
    def enforce(self, policy: AbstractSecurityPolicy, context: Dict[str, Any]) -> Dict[str, Any]:
        """Enforce security policy"""
        pass
    
    @abstractmethod
    def get_enforcement_actions(self) -> List[str]:
        """Get supported enforcement actions"""
        pass
    
    def add_policy(self, policy_name: str, policy: AbstractSecurityPolicy):
        """Add policy"""
        self.policies[policy_name] = policy
    
    def remove_policy(self, policy_name: str):
        """Remove policy"""
        if policy_name in self.policies:
            del self.policies[policy_name]
    
    def set_config(self, config: Dict[str, Any]):
        """Set enforcer configuration"""
        self.config = config


class AbstractSecurityCache(ABC):
    """Abstract base class for security cache"""
    
    def __init__(self, cache_type: str):
        self.cache_type = cache_type
        self.config = {}
    
    @abstractmethod
    def get(self, key: str) -> Any:
        """Get value from cache"""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """Clear cache"""
        pass
    
    def set_config(self, config: Dict[str, Any]):
        """Set cache configuration"""
        self.config = config


class SecurityLogger(ABC):
    """Abstract base class for security loggers"""
    
    def __init__(self, logger_type: str):
        self.logger_type = logger_type
        self.config = {}
    
    @abstractmethod
    def log(self, level: str, message: str, context: Dict[str, Any] = None):
        """Log security event"""
        pass
    
    @abstractmethod
    def get_log_levels(self) -> List[str]:
        """Get supported log levels"""
        pass
    
    def set_config(self, config: Dict[str, Any]):
        """Set logger configuration"""
        self.config = config


class AbstractSecurityMetrics(ABC):
    """Abstract base class for security metrics"""
    
    def __init__(self, metrics_type: str):
        self.metrics_type = metrics_type
        self.config = {}
    
    @abstractmethod
    def collect(self) -> Dict[str, Any]:
        """Collect security metrics"""
        pass
    
    @abstractmethod
    def get_metric_types(self) -> List[str]:
        """Get supported metric types"""
        pass
    
    def set_config(self, config: Dict[str, Any]):
        """Set metrics configuration"""
        self.config = config


# Export symbols
__all__ = [
    'SecurityModel',
    'UserSecurityModel',
    'TenantSecurityModel',
    'AbstractSecurityService',
    'SecurityValidator',
    'SecurityAnalyzer',
    'SecurityDetector',
    'SecurityReporter',
    'AbstractSecurityMonitor',
    'SecurityFilter',
    'SecurityProcessor',
    'SecurityTransformer',
    'SecurityRepository',
    'SecurityUseCase',
    'SecurityInteractor',
    'SecurityEventHandler',
    'SecurityNotifier',
    'SecurityAuditor',
    'AbstractSecurityPolicy',
    'SecurityEnforcer',
    'AbstractSecurityCache',
    'SecurityLogger',
    'AbstractSecurityMetrics'
]