# =============================================================================
# fraud_detection/events.py
# =============================================================================
"""
Event System for Fraud Detection System.

Provides comprehensive event management for fraud detection
workflows, audit trails, and real-time processing.
"""

from __future__ import annotations

import logging
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from abc import ABC, abstractmethod

from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.dispatch import Signal

from api.fraud_detection.exceptions import EventError
from api.fraud_detection.signals_cap import capital_signal_manager


logger = logging.getLogger(__name__)


class EventType(Enum):
    """Event types for fraud detection system."""
    FRAUD_DETECTED = "fraud_detected"
    CASE_CREATED = "case_created"
    CASE_UPDATED = "case_updated"
    CASE_ESCALATED = "case_escalated"
    ALERT_GENERATED = "alert_generated"
    RISK_SCORE_CHANGED = "risk_score_changed"
    SANCTIONS_FLAGGED = "sanctions_flagged"
    COMPLIANCE_CHECK = "compliance_check"
    REGULATORY_BREACH = "regulatory_breach"
    FINANCIAL_LOSS = "financial_loss"
    USER_SUSPENDED = "user_suspended"
    TRANSACTION_BLOCKED = "transaction_blocked"
    SYSTEM_ALERT = "system_alert"
    AUDIT_EVENT = "audit_event"
    KNOWLEDGE_UPDATED = "knowledge_updated"
    PATTERN_LEARNED = "pattern_learned"
    MODEL_TRAINED = "model_trained"
    MODEL_DEPLOYED = "model_deployed"


class EventSeverity(Enum):
    """Event severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FraudEvent:
    """Core event data structure for fraud detection."""
    event_id: str
    event_type: EventType
    severity: EventSeverity
    title: str
    description: str
    user_id: Optional[Union[int, str]] = None
    case_id: Optional[Union[int, str]] = None
    alert_id: Optional[Union[int, str]] = None
    transaction_id: Optional[str] = None
    ip_address: Optional[str] = None
    device_fingerprint: Optional[str] = None
    risk_score: Optional[int] = None
    financial_impact: Optional[float] = None
    regulatory_impact: bool = False
    requires_action: bool = False
    action_deadline: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = None
    processed_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = timezone.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['severity'] = self.severity.value
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        if self.processed_at:
            data['processed_at'] = self.processed_at.isoformat()
        if self.action_deadline:
            data['action_deadline'] = self.action_deadline.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FraudEvent':
        """Create event from dictionary."""
        if 'event_type' in data:
            data['event_type'] = EventType(data['event_type'])
        if 'severity' in data:
            data['severity'] = EventSeverity(data['severity'])
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'processed_at' in data and isinstance(data['processed_at'], str):
            data['processed_at'] = datetime.fromisoformat(data['processed_at'])
        if 'action_deadline' in data and isinstance(data['action_deadline'], str):
            data['action_deadline'] = datetime.fromisoformat(data['action_deadline'])
        
        return cls(**data)


class EventHandler(ABC):
    """Abstract base class for event handlers."""
    
    @abstractmethod
    def handle(self, event: FraudEvent) -> bool:
        """
        Handle fraud event.
        
        Args:
            event: Fraud event to handle
            
        Returns:
            True if handled successfully
        """
        pass
    
    @abstractmethod
    def can_handle(self, event: FraudEvent) -> bool:
        """
        Check if handler can process event.
        
        Args:
            event: Fraud event
            
        Returns:
            True if handler can process event
        """
        pass


class EventProcessor:
    """
    Main event processor for fraud detection system.
    
    Handles event creation, processing, routing, and persistence.
    """
    
    def __init__(self):
        """Initialize event processor."""
        self.handlers: List[EventHandler] = []
        self.event_history: List[FraudEvent] = []
        self.max_history = getattr(settings, 'FRAUD_EVENT_MAX_HISTORY', 10000)
        self.processing_queue: List[FraudEvent] = []
        self.max_queue_size = getattr(settings, 'FRAUD_EVENT_MAX_QUEUE', 1000)
        self.is_processing = False
        
        # Register default handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default event handlers."""
        self.register_handler(NotificationHandler())
        self.register_handler(AuditHandler())
        self.register_handler(MetricsHandler())
        self.register_handler(CapitalEventHandler())
        self.register_handler(ActionHandler())
    
    def register_handler(self, handler: EventHandler):
        """Register event handler."""
        self.handlers.append(handler)
        logger.info(f"Registered event handler: {handler.__class__.__name__}")
    
    def create_event(self, event_type: EventType, title: str, description: str,
                    severity: EventSeverity = EventSeverity.MEDIUM,
                    **kwargs) -> FraudEvent:
        """
        Create new fraud event.
        
        Args:
            event_type: Type of event
            title: Event title
            description: Event description
            severity: Event severity
            **kwargs: Additional event data
            
        Returns:
            Created event
        """
        event_id = f"evt_{timezone.now().strftime('%Y%m%d_%H%M%S')}_{hash(description)}"
        
        event = FraudEvent(
            event_id=event_id,
            event_type=event_type,
            severity=severity,
            title=title,
            description=description,
            **kwargs
        )
        
        # Add to processing queue
        self._queue_event(event)
        
        logger.info(f"Created fraud event: {event_id} - {title}")
        return event
    
    def _queue_event(self, event: FraudEvent):
        """Add event to processing queue."""
        if len(self.processing_queue) >= self.max_queue_size:
            # Remove oldest event
            removed_event = self.processing_queue.pop(0)
            logger.warning(f"Event queue full, removed oldest event: {removed_event.event_id}")
        
        self.processing_queue.append(event)
        
        # Process events asynchronously
        if not self.is_processing:
            self._process_events_async()
    
    def _process_events_async(self):
        """Process events asynchronously."""
        # This would typically use Celery or similar
        # For now, process synchronously
        self.process_events()
    
    def process_events(self) -> int:
        """
        Process all events in queue.
        
        Returns:
            Number of events processed
        """
        if self.is_processing:
            return 0
        
        self.is_processing = True
        processed_count = 0
        
        try:
            while self.processing_queue:
                event = self.processing_queue.pop(0)
                
                try:
                    self._process_single_event(event)
                    processed_count += 1
                except Exception as e:
                    logger.error(f"Error processing event {event.event_id}: {e}")
                    
                    # Add to failed events queue for retry
                    self._handle_failed_event(event, e)
        
        finally:
            self.is_processing = False
        
        logger.info(f"Processed {processed_count} fraud events")
        return processed_count
    
    def _process_single_event(self, event: FraudEvent):
        """Process single event."""
        event.processed_at = timezone.now()
        
        # Find and execute handlers
        handlers_executed = 0
        for handler in self.handlers:
            if handler.can_handle(event):
                try:
                    success = handler.handle(event)
                    if success:
                        handlers_executed += 1
                except Exception as e:
                    logger.error(f"Handler {handler.__class__.__name__} failed for event {event.event_id}: {e}")
        
        if handlers_executed == 0:
            logger.warning(f"No handlers found for event {event.event_id}")
        
        # Add to history
        self._add_to_history(event)
    
    def _handle_failed_event(self, event: FraudEvent, error: Exception):
        """Handle failed event processing."""
        logger.error(f"Failed to process event {event.event_id}: {error}")
        
        # Create system alert for critical events
        if event.severity in [EventSeverity.HIGH, EventSeverity.CRITICAL]:
            self.create_event(
                event_type=EventType.SYSTEM_ALERT,
                title=f"Event Processing Failed: {event.event_id}",
                description=f"Failed to process fraud event: {error}",
                severity=EventSeverity.HIGH,
                metadata={
                    'failed_event_id': event.event_id,
                    'error': str(error),
                    'original_event': event.to_dict()
                }
            )
    
    def _add_to_history(self, event: FraudEvent):
        """Add event to history."""
        self.event_history.append(event)
        
        # Trim history if needed
        if len(self.event_history) > self.max_history:
            self.event_history = self.event_history[-self.max_history:]
    
    def get_event_history(self, event_type: Optional[EventType] = None,
                         severity: Optional[EventSeverity] = None,
                         user_id: Optional[Union[int, str]] = None,
                         limit: int = 100) -> List[FraudEvent]:
        """
        Get event history with filters.
        
        Args:
            event_type: Filter by event type
            severity: Filter by severity
            user_id: Filter by user ID
            limit: Maximum number of events
            
        Returns:
            Filtered event list
        """
        events = self.event_history
        
        # Apply filters
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if severity:
            events = [e for e in events if e.severity == severity]
        
        if user_id:
            events = [e for e in events if e.user_id == user_id]
        
        # Sort by creation time (newest first)
        events.sort(key=lambda e: e.created_at, reverse=True)
        
        return events[:limit]
    
    def get_pending_actions(self) -> List[FraudEvent]:
        """Get events requiring action."""
        return [
            event for event in self.event_history
            if event.requires_action and (
                not event.action_deadline or 
                event.action_deadline > timezone.now()
            )
        ]
    
    def get_overdue_actions(self) -> List[FraudEvent]:
        """Get overdue actions."""
        return [
            event for event in self.event_history
            if event.requires_action and 
            event.action_deadline and 
            event.action_deadline <= timezone.now()
        ]


# Event handlers
class NotificationHandler(EventHandler):
    """Handler for event notifications."""
    
    def handle(self, event: FraudEvent) -> bool:
        """Handle event notifications."""
        try:
            # Send notification based on severity
            if event.severity in [EventSeverity.HIGH, EventSeverity.CRITICAL]:
                from api.fraud_detection.notifications_push import send_system_alert
                send_system_alert({
                    'alert_type': event.event_type.value,
                    'message': event.title,
                    'description': event.description,
                    'severity': event.severity.value,
                    'user_id': event.user_id,
                    'case_id': event.case_id,
                    'financial_impact': event.financial_impact,
                    'requires_immediate_action': event.requires_action
                }, priority='high' if event.severity == EventSeverity.CRITICAL else 'medium')
            
            return True
            
        except Exception as e:
            logger.error(f"Notification handler failed: {e}")
            return False
    
    def can_handle(self, event: FraudEvent) -> bool:
        """Check if can handle event."""
        return event.severity in [EventSeverity.MEDIUM, EventSeverity.HIGH, EventSeverity.CRITICAL]


class AuditHandler(EventHandler):
    """Handler for event auditing."""
    
    def handle(self, event: FraudEvent) -> bool:
        """Handle event auditing."""
        try:
            # Log event for audit trail
            audit_data = {
                'event_id': event.event_id,
                'event_type': event.event_type.value,
                'severity': event.severity.value,
                'title': event.title,
                'description': event.description,
                'user_id': event.user_id,
                'case_id': event.case_id,
                'transaction_id': event.transaction_id,
                'ip_address': event.ip_address,
                'risk_score': event.risk_score,
                'financial_impact': event.financial_impact,
                'regulatory_impact': event.regulatory_impact,
                'requires_action': event.requires_action,
                'created_at': event.created_at.isoformat(),
                'metadata': event.metadata
            }
            
            logger.info(f"AUDIT EVENT: {audit_data}")
            
            # Store in audit log (simplified)
            # In practice, this would save to database
            return True
            
        except Exception as e:
            logger.error(f"Audit handler failed: {e}")
            return False
    
    def can_handle(self, event: FraudEvent) -> bool:
        """Check if can handle event."""
        return True  # Handle all events for audit


class MetricsHandler(EventHandler):
    """Handler for event metrics collection."""
    
    def handle(self, event: FraudEvent) -> bool:
        """Handle event metrics."""
        try:
            from api.fraud_detection.monitoring import record_fraud_metric
            
            # Record event metrics
            record_fraud_metric('fraud_event', 1, {
                'event_type': event.event_type.value,
                'severity': event.severity.value,
                'user_id': event.user_id,
                'case_id': event.case_id,
                'risk_score': event.risk_score,
                'financial_impact': event.financial_impact,
                'regulatory_impact': event.regulatory_impact,
                'requires_action': event.requires_action
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Metrics handler failed: {e}")
            return False
    
    def can_handle(self, event: FraudEvent) -> bool:
        """Check if can handle event."""
        return True  # Handle all events for metrics


class CapitalEventHandler(EventHandler):
    """Handler for capital-level events."""
    
    def handle(self, event: FraudEvent) -> bool:
        """Handle capital events."""
        try:
            # Send capital signal for critical events
            if event.severity == EventSeverity.CRITICAL:
                from api.fraud_detection.signals_cap import send_major_fraud_signal
                
                send_major_fraud_signal(
                    description=event.description,
                    affected_entities=[
                        f"user:{event.user_id}" if event.user_id else "system",
                        f"case:{event.case_id}" if event.case_id else None
                    ],
                    financial_impact=event.financial_impact,
                    metadata={
                        'event_id': event.event_id,
                        'event_type': event.event_type.value,
                        'event_data': event.to_dict()
                    }
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Capital event handler failed: {e}")
            return False
    
    def can_handle(self, event: FraudEvent) -> bool:
        """Check if can handle event."""
        return event.severity == EventSeverity.CRITICAL


class ActionHandler(EventHandler):
    """Handler for event actions."""
    
    def handle(self, event: FraudEvent) -> bool:
        """Handle event actions."""
        try:
            if event.requires_action:
                # Schedule action if deadline exists
                if event.action_deadline:
                    self._schedule_action(event)
                
                # Create follow-up event if needed
                if event.severity == EventSeverity.CRITICAL:
                    from api.fraud_detection.events import event_processor
                    event_processor.create_event(
                        event_type=EventType.SYSTEM_ALERT,
                        title=f"Action Required: {event.title}",
                        description=f"Action required for event: {event.event_id}",
                        severity=EventSeverity.HIGH,
                        metadata={
                            'parent_event_id': event.event_id,
                            'action_deadline': event.action_deadline.isoformat() if event.action_deadline else None
                        }
                    )
            
            return True
            
        except Exception as e:
            logger.error(f"Action handler failed: {e}")
            return False
    
    def can_handle(self, event: FraudEvent) -> bool:
        """Check if can handle event."""
        return event.requires_action
    
    def _schedule_action(self, event: FraudEvent):
        """Schedule action for event."""
        # This would integrate with task scheduler
        # For now, just log the scheduled action
        logger.info(f"Action scheduled for event {event.event_id} by {event.action_deadline}")


# Global event processor
event_processor = EventProcessor()


# Convenience functions for creating events
def create_fraud_detected_event(user_id: Union[int, str], description: str,
                               risk_score: int, **kwargs) -> FraudEvent:
    """Create fraud detected event."""
    return event_processor.create_event(
        event_type=EventType.FRAUD_DETECTED,
        title="Fraud Detected",
        description=description,
        severity=EventSeverity.HIGH if risk_score >= 70 else EventSeverity.MEDIUM,
        user_id=user_id,
        risk_score=risk_score,
        **kwargs
    )


def create_case_created_event(case_id: Union[int, str], user_id: Union[int, str],
                             description: str, **kwargs) -> FraudEvent:
    """Create case created event."""
    return event_processor.create_event(
        event_type=EventType.CASE_CREATED,
        title="Fraud Case Created",
        description=description,
        severity=EventSeverity.MEDIUM,
        case_id=case_id,
        user_id=user_id,
        **kwargs
    )


def create_alert_generated_event(alert_id: Union[int, str], user_id: Union[int, str],
                               description: str, severity: EventSeverity, **kwargs) -> FraudEvent:
    """Create alert generated event."""
    return event_processor.create_event(
        event_type=EventType.ALERT_GENERATED,
        title="Fraud Alert Generated",
        description=description,
        severity=severity,
        alert_id=alert_id,
        user_id=user_id,
        **kwargs
    )


def create_regulatory_breach_event(description: str, financial_impact: float,
                                  **kwargs) -> FraudEvent:
    """Create regulatory breach event."""
    return event_processor.create_event(
        event_type=EventType.REGULATORY_BREACH,
        title="Regulatory Breach",
        description=description,
        severity=EventSeverity.CRITICAL,
        financial_impact=financial_impact,
        regulatory_impact=True,
        requires_action=True,
        action_deadline=timezone.now() + timedelta(hours=24),
        **kwargs
    )


def create_transaction_blocked_event(user_id: Union[int, str], transaction_id: str,
                                   description: str, **kwargs) -> FraudEvent:
    """Create transaction blocked event."""
    return event_processor.create_event(
        event_type=EventType.TRANSACTION_BLOCKED,
        title="Transaction Blocked",
        description=description,
        severity=EventSeverity.HIGH,
        user_id=user_id,
        transaction_id=transaction_id,
        **kwargs
    )


# Event statistics and reporting
def get_event_statistics(days: int = 30) -> Dict[str, Any]:
    """Get event statistics."""
    cutoff_date = timezone.now() - timedelta(days=days)
    
    recent_events = [
        event for event in event_processor.event_history
        if event.created_at >= cutoff_date
    ]
    
    # Count by type
    type_counts = {}
    for event in recent_events:
        event_type = event.event_type.value
        type_counts[event_type] = type_counts.get(event_type, 0) + 1
    
    # Count by severity
    severity_counts = {}
    for event in recent_events:
        severity = event.severity.value
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
    
    # Financial impact
    total_financial_impact = sum(
        event.financial_impact or 0
        for event in recent_events
    )
    
    # Actions required
    actions_required = len([
        event for event in recent_events
        if event.requires_action
    ])
    
    # Overdue actions
    overdue_actions = len([
        event for event in recent_events
        if event.requires_action and event.action_deadline and event.action_deadline <= timezone.now()
    ])
    
    return {
        'period_days': days,
        'total_events': len(recent_events),
        'events_by_type': type_counts,
        'events_by_severity': severity_counts,
        'total_financial_impact': total_financial_impact,
        'actions_required': actions_required,
        'overdue_actions': overdue_actions,
        'regulatory_impact_events': len([
            event for event in recent_events
            if event.regulatory_impact
        ])
    }


# Event cleanup and maintenance
def cleanup_old_events(days: int = 90) -> int:
    """Clean up old events from history."""
    cutoff_date = timezone.now() - timedelta(days=days)
    
    original_count = len(event_processor.event_history)
    event_processor.event_history = [
        event for event in event_processor.event_history
        if event.created_at >= cutoff_date
    ]
    
    cleaned_count = original_count - len(event_processor.event_history)
    
    logger.info(f"Cleaned up {cleaned_count} old events (older than {days} days)")
    return cleaned_count


# ---------------------------------------------------------------------------
# Additional convenience functions — none map onto existing FraudEvent
# fields besides description/metadata, so extra context goes into metadata.
# ---------------------------------------------------------------------------

def create_knowledge_updated_event(entity_id, entity_type, description,
                                    changes=None, metadata=None, **kwargs) -> FraudEvent:
    meta = dict(metadata or {})
    meta.update({'entity_id': entity_id, 'entity_type': entity_type, 'changes': changes})
    return event_processor.create_event(
        event_type=EventType.KNOWLEDGE_UPDATED, title="Knowledge Base Updated",
        description=description, severity=EventSeverity.LOW, metadata=meta, **kwargs
    )


def create_pattern_learned_event(pattern_type, confidence, description,
                                  pattern_data=None, metadata=None, **kwargs) -> FraudEvent:
    meta = dict(metadata or {})
    meta.update({'pattern_type': pattern_type, 'confidence': confidence, 'pattern_data': pattern_data})
    return event_processor.create_event(
        event_type=EventType.PATTERN_LEARNED, title="Fraud Pattern Learned",
        description=description, severity=EventSeverity.LOW, metadata=meta, **kwargs
    )


def create_model_trained_event(model_type, performance, training_data_size, description,
                                metadata=None, **kwargs) -> FraudEvent:
    meta = dict(metadata or {})
    meta.update({'model_type': model_type, 'performance': performance, 'training_data_size': training_data_size})
    return event_processor.create_event(
        event_type=EventType.MODEL_TRAINED, title="Fraud Model Trained",
        description=description, severity=EventSeverity.LOW, metadata=meta, **kwargs
    )


def create_model_deployed_event(model_type, description, metadata=None, **kwargs) -> FraudEvent:
    meta = dict(metadata or {})
    meta.update({'model_type': model_type})
    return event_processor.create_event(
        event_type=EventType.MODEL_DEPLOYED, title="Fraud Model Deployed",
        description=description, severity=EventSeverity.MEDIUM, metadata=meta, **kwargs
    )
