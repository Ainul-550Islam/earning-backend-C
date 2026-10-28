"""
Abstract base classes for alerts app
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from django.db import models
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class AlertProcessor(ABC):
    """Abstract base class for alert processors"""
    
    @abstractmethod
    def process_alert(self, alert_data: Dict[str, Any]) -> bool:
        """Process an alert and return success status"""
        pass
    
    @abstractmethod
    def validate_alert_data(self, alert_data: Dict[str, Any]) -> bool:
        """Validate alert data before processing"""
        pass
    
    @abstractmethod
    def get_processor_info(self) -> Dict[str, Any]:
        """Get processor information"""
        pass
    
    def pre_process(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Pre-process alert data"""
        return alert_data
    
    def post_process(self, alert_data: Dict[str, Any], result: bool) -> Dict[str, Any]:
        """Post-process alert data"""
        return alert_data


class NotificationChannel(ABC):
    """Abstract base class for notification channels"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
        self.enabled = config.get('enabled', True)
    
    @abstractmethod
    def send(self, recipient: str, message: str, subject: str = None) -> bool:
        """Send notification to recipient"""
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Validate channel configuration"""
        pass
    
    @abstractmethod
    def get_channel_info(self) -> Dict[str, Any]:
        """Get channel information"""
        pass
    
    def is_available(self) -> bool:
        """Check if channel is available"""
        return self.enabled and self.validate_config()
    
    def format_message(self, message: str, context: Dict[str, Any] = None) -> str:
        """Format message with context"""
        if not context:
            return message
        
        try:
            return message.format(**context)
        except KeyError as e:
            logger.error(f"Missing context key in message format: {e}")
            return message


class AlertFilter(ABC):
    """Abstract base class for alert filters"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
        self.enabled = config.get('enabled', True)
    
    @abstractmethod
    def should_suppress(self, alert_data: Dict[str, Any]) -> bool:
        """Determine if alert should be suppressed"""
        pass
    
    @abstractmethod
    def get_filter_info(self) -> Dict[str, Any]:
        """Get filter information"""
        pass
    
    def get_priority(self) -> int:
        """Get filter priority (higher = processed first)"""
        return self.config.get('priority', 0)
    
    def is_enabled(self) -> bool:
        """Check if filter is enabled"""
        return self.enabled


class AlertAggregator(ABC):
    """Abstract base class for alert aggregators"""
    
    @abstractmethod
    def aggregate_alerts(self, alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate multiple alerts into summary"""
        pass
    
    @abstractmethod
    def get_aggregation_rules(self) -> List[Dict[str, Any]]:
        """Get aggregation rules"""
        pass
    
    def should_aggregate(self, alert_data: Dict[str, Any]) -> bool:
        """Check if alert should be aggregated"""
        return True


class AlertEscalator(ABC):
    """Abstract base class for alert escalators"""
    
    @abstractmethod
    def escalate_alert(self, alert_data: Dict[str, Any], escalation_level: int) -> bool:
        """Escalate alert to next level"""
        pass
    
    @abstractmethod
    def get_escalation_rules(self) -> List[Dict[str, Any]]:
        """Get escalation rules"""
        pass
    
    @abstractmethod
    def get_max_escalation_level(self) -> int:
        """Get maximum escalation level"""
        pass
    
    def should_escalate(self, alert_data: Dict[str, Any]) -> bool:
        """Check if alert should be escalated"""
        return not alert_data.get('is_resolved', False)


class AlertReporter(ABC):
    """Abstract base class for alert reporters"""
    
    @abstractmethod
    def generate_report(self, report_config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate alert report"""
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """Get supported report formats"""
        pass
    
    @abstractmethod
    def get_report_types(self) -> List[str]:
        """Get available report types"""
        pass


class AlertAnalytics(ABC):
    """Abstract base class for alert analytics"""
    
    @abstractmethod
    def analyze_alerts(self, alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze alert patterns and trends"""
        pass
    
    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        pass
    
    @abstractmethod
    def get_analytics_types(self) -> List[str]:
        """Get supported analytics types"""
        pass


class AlertStorage(ABC):
    """Abstract base class for alert storage"""
    
    @abstractmethod
    def store_alert(self, alert_data: Dict[str, Any]) -> str:
        """Store alert and return ID"""
        pass
    
    @abstractmethod
    def retrieve_alert(self, alert_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve alert by ID"""
        pass
    
    @abstractmethod
    def update_alert(self, alert_id: str, updates: Dict[str, Any]) -> bool:
        """Update alert"""
        pass
    
    @abstractmethod
    def delete_alert(self, alert_id: str) -> bool:
        """Delete alert"""
        pass
    
    @abstractmethod
    def query_alerts(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query alerts with filters"""
        pass


class AlertValidator(ABC):
    """Abstract base class for alert validators"""
    
    @abstractmethod
    def validate(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate alert data and return result"""
        pass
    
    @abstractmethod
    def get_validation_rules(self) -> List[Dict[str, Any]]:
        """Get validation rules"""
        pass
    
    def is_valid(self, alert_data: Dict[str, Any]) -> bool:
        """Check if alert data is valid"""
        result = self.validate(alert_data)
        return result.get('valid', False)


class AlertTransformer(ABC):
    """Abstract base class for alert transformers"""
    
    @abstractmethod
    def transform(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform alert data"""
        pass
    
    @abstractmethod
    def get_transformation_rules(self) -> List[Dict[str, Any]]:
        """Get transformation rules"""
        pass
    
    def can_transform(self, alert_data: Dict[str, Any]) -> bool:
        """Check if alert can be transformed"""
        return True


class AlertEnricher(ABC):
    """Abstract base class for alert enrichers"""
    
    @abstractmethod
    def enrich(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich alert data with additional information"""
        pass
    
    @abstractmethod
    def get_enrichment_sources(self) -> List[str]:
        """Get enrichment data sources"""
        pass
    
    def should_enrich(self, alert_data: Dict[str, Any]) -> bool:
        """Check if alert should be enriched"""
        return True


class AlertCorrelator(ABC):
    """Abstract base class for alert correlation"""
    
    @abstractmethod
    def correlate_alerts(self, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Correlate related alerts"""
        pass
    
    @abstractmethod
    def get_correlation_rules(self) -> List[Dict[str, Any]]:
        """Get correlation rules"""
        pass
    
    def find_related_alerts(self, alert_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find alerts related to given alert"""
        return []


class AlertDeduplicator(ABC):
    """Abstract base class for alert deduplication"""
    
    @abstractmethod
    def deduplicate(self, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate alerts"""
        pass
    
    @abstractmethod
    def get_deduplication_key(self, alert_data: Dict[str, Any]) -> str:
        """Get deduplication key for alert"""
        pass
    
    def is_duplicate(self, alert_data: Dict[str, Any], existing_alerts: List[Dict[str, Any]]) -> bool:
        """Check if alert is duplicate"""
        key = self.get_deduplication_key(alert_data)
        for existing in existing_alerts:
            if self.get_deduplication_key(existing) == key:
                return True
        return False


class AlertScheduler(ABC):
    """Abstract base class for alert scheduling"""
    
    @abstractmethod
    def schedule_alert(self, alert_data: Dict[str, Any], schedule_time: timezone.datetime) -> str:
        """Schedule alert for future delivery"""
        pass
    
    @abstractmethod
    def cancel_scheduled_alert(self, schedule_id: str) -> bool:
        """Cancel scheduled alert"""
        pass
    
    @abstractmethod
    def get_scheduled_alerts(self) -> List[Dict[str, Any]]:
        """Get all scheduled alerts"""
        pass
    
    def should_schedule(self, alert_data: Dict[str, Any]) -> bool:
        """Check if alert should be scheduled"""
        return False


class AlertMetricsCollector(ABC):
    """Abstract base class for metrics collection"""
    
    @abstractmethod
    def collect_metrics(self) -> Dict[str, Any]:
        """Collect alert metrics"""
        pass
    
    @abstractmethod
    def get_metric_definitions(self) -> List[Dict[str, Any]]:
        """Get metric definitions"""
        pass
    
    def should_collect(self) -> bool:
        """Check if metrics should be collected"""
        return True


class AlertHealthChecker(ABC):
    """Abstract base class for health checking"""
    
    @abstractmethod
    def check_health(self) -> Dict[str, Any]:
        """Check system health"""
        pass
    
    @abstractmethod
    def get_health_checks(self) -> List[Dict[str, Any]]:
        """Get health check definitions"""
        pass
    
    def is_healthy(self) -> bool:
        """Check if system is healthy"""
        health_result = self.check_health()
        return health_result.get('status') == 'healthy'


class AlertConfigManager(ABC):
    """Abstract base class for configuration management"""
    
    @abstractmethod
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        pass
    
    @abstractmethod
    def set_config(self, key: str, value: Any) -> bool:
        """Set configuration value"""
        pass
    
    @abstractmethod
    def delete_config(self, key: str) -> bool:
        """Delete configuration value"""
        pass
    
    @abstractmethod
    def get_all_configs(self) -> Dict[str, Any]:
        """Get all configuration values"""
        pass


class AlertSecurityManager(ABC):
    """Abstract base class for security management"""
    
    @abstractmethod
    def authenticate_user(self, credentials: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Authenticate user"""
        pass
    
    @abstractmethod
    def authorize_action(self, user: Dict[str, Any], action: str, resource: str) -> bool:
        """Authorize user action"""
        pass
    
    @abstractmethod
    def audit_action(self, user: Dict[str, Any], action: str, resource: str, details: Dict[str, Any]) -> bool:
        """Audit user action"""
        pass


class AlertBackupManager(ABC):
    """Abstract base class for backup management"""
    
    @abstractmethod
    def create_backup(self, backup_config: Dict[str, Any]) -> str:
        """Create backup and return backup ID"""
        pass
    
    @abstractmethod
    def restore_backup(self, backup_id: str) -> bool:
        """Restore from backup"""
        pass
    
    @abstractmethod
    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backups"""
        pass
    
    @abstractmethod
    def delete_backup(self, backup_id: str) -> bool:
        """Delete backup"""
        pass


class AlertMigrationManager(ABC):
    """Abstract base class for data migration"""
    
    @abstractmethod
    def migrate_data(self, migration_config: Dict[str, Any]) -> bool:
        """Migrate data"""
        pass
    
    @abstractmethod
    def rollback_migration(self, migration_id: str) -> bool:
        """Rollback migration"""
        pass
    
    @abstractmethod
    def get_migration_history(self) -> List[Dict[str, Any]]:
        """Get migration history"""
        pass


# Factory classes for creating instances
class AlertProcessorFactory:
    """Factory for creating alert processors"""
    
    _processors = {}
    
    @classmethod
    def register_processor(cls, name: str, processor_class: type):
        """Register a processor class"""
        cls._processors[name] = processor_class
    
    @classmethod
    def create_processor(cls, name: str, config: Dict[str, Any]) -> Optional[AlertProcessor]:
        """Create processor instance"""
        if name not in cls._processors:
            logger.error(f"Unknown processor: {name}")
            return None
        
        processor_class = cls._processors[name]
        return processor_class(config)
    
    @classmethod
    def get_available_processors(cls) -> List[str]:
        """Get list of available processors"""
        return list(cls._processors.keys())


class NotificationChannelFactory:
    """Factory for creating notification channels"""
    
    _channels = {}
    
    @classmethod
    def register_channel(cls, name: str, channel_class: type):
        """Register a channel class"""
        cls._channels[name] = channel_class
    
    @classmethod
    def create_channel(cls, name: str, config: Dict[str, Any]) -> Optional[NotificationChannel]:
        """Create channel instance"""
        if name not in cls._channels:
            logger.error(f"Unknown channel: {name}")
            return None
        
        channel_class = cls._channels[name]
        return channel_class(config)
    
    @classmethod
    def get_available_channels(cls) -> List[str]:
        """Get list of available channels"""
        return list(cls._channels.keys())
