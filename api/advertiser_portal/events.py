"""
Event System for Advertiser Portal

This module provides an event-driven architecture for handling
business events and decoupling system components.
"""

import logging
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import json
import uuid

from django.utils import timezone
from django.db import transaction
from django.core.serializers.json import DjangoJSONEncoder

from .exceptions import *
from .utils import *


logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Event priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


class EventStatus(Enum):
    """Event processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Event:
    """Base event class."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=timezone.now)
    priority: EventPriority = EventPriority.NORMAL
    status: EventStatus = EventStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    delay_until: Optional[datetime] = None
    
    def __post_init__(self):
        """Post-initialization processing."""
        if not self.event_type:
            self.event_type = self.__class__.__name__
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'data': self.data,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat(),
            'priority': self.priority.value,
            'status': self.status.value,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'delay_until': self.delay_until.isoformat() if self.delay_until else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create event from dictionary."""
        event = cls(
            event_id=data.get('event_id', str(uuid.uuid4())),
            event_type=data.get('event_type', ''),
            data=data.get('data', {}),
            metadata=data.get('metadata', {}),
            timestamp=datetime.fromisoformat(data['timestamp']) if data.get('timestamp') else timezone.now(),
            priority=EventPriority(data.get('priority', EventPriority.NORMAL.value)),
            status=EventStatus(data.get('status', EventStatus.PENDING.value)),
            retry_count=data.get('retry_count', 0),
            max_retries=data.get('max_retries', 3)
        )
        
        if data.get('delay_until'):
            event.delay_until = datetime.fromisoformat(data['delay_until'])
        
        return event


# Domain Events
@dataclass
class AdvertiserCreatedEvent(Event):
    """Event raised when advertiser is created."""
    advertiser_id: str = ""
    company_name: str = ""
    contact_email: str = ""
    
    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'advertiser_id': self.advertiser_id,
            'company_name': self.company_name,
            'contact_email': self.contact_email
        })


@dataclass
class AdvertiserVerifiedEvent(Event):
    """Event raised when advertiser is verified."""
    advertiser_id: str = ""
    verified_by: str = ""
    
    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'advertiser_id': self.advertiser_id,
            'verified_by': self.verified_by
        })


@dataclass
class CampaignCreatedEvent(Event):
    """Event raised when campaign is created."""
    campaign_id: str = ""
    advertiser_id: str = ""
    name: str = ""
    objective: str = ""
    
    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'campaign_id': self.campaign_id,
            'advertiser_id': self.advertiser_id,
            'name': self.name,
            'objective': self.objective
        })


@dataclass
class CampaignStatusChangedEvent(Event):
    """Event raised when campaign status changes."""
    campaign_id: str = ""
    old_status: str = ""
    new_status: str = ""
    changed_by: str = ""
    
    def __post_init__(self):
        super().__post_init__()
        self.priority = EventPriority.HIGH
        self.data.update({
            'campaign_id': self.campaign_id,
            'old_status': self.old_status,
            'new_status': self.new_status,
            'changed_by': self.changed_by
        })


@dataclass
class CreativeUploadedEvent(Event):
    """Event raised when creative is uploaded."""
    creative_id: str = ""
    campaign_id: str = ""
    creative_type: str = ""
    file_size: int = 0
    
    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'creative_id': self.creative_id,
            'campaign_id': self.campaign_id,
            'creative_type': self.creative_type,
            'file_size': self.file_size
        })


@dataclass
class CreativeApprovedEvent(Event):
    """Event raised when creative is approved."""
    creative_id: str = ""
    campaign_id: str = ""
    approved_by: str = ""
    
    def __post_init__(self):
        super().__post_init__()
        self.priority = EventPriority.HIGH
        self.data.update({
            'creative_id': self.creative_id,
            'campaign_id': self.campaign_id,
            'approved_by': self.approved_by
        })


@dataclass
class BudgetThresholdReachedEvent(Event):
    """Event raised when budget threshold is reached."""
    campaign_id: str = ""
    advertiser_id: str = ""
    threshold: int = 0
    current_utilization: float = 0.0
    
    def __post_init__(self):
        super().__post_init__()
        self.priority = EventPriority.HIGH
        self.data.update({
            'campaign_id': self.campaign_id,
            'advertiser_id': self.advertiser_id,
            'threshold': self.threshold,
            'current_utilization': self.current_utilization
        })


@dataclass
class PaymentProcessedEvent(Event):
    """Event raised when payment is processed."""
    transaction_id: str = ""
    advertiser_id: str = ""
    amount: float = 0.0
    payment_method: str = ""
    
    def __post_init__(self):
        super().__post_init__()
        self.priority = EventPriority.HIGH
        self.data.update({
            'transaction_id': self.transaction_id,
            'advertiser_id': self.advertiser_id,
            'amount': self.amount,
            'payment_method': self.payment_method
        })


@dataclass
class FraudDetectedEvent(Event):
    """Event raised when fraud is detected."""
    fraud_type: str = ""
    risk_score: int = 0
    ip_address: str = ""
    user_agent: str = ""
    
    def __post_init__(self):
        super().__post_init__()
        self.priority = EventPriority.URGENT
        self.data.update({
            'fraud_type': self.fraud_type,
            'risk_score': self.risk_score,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent
        })


@dataclass
class InvoiceGeneratedEvent(Event):
    """Event raised when invoice is generated."""
    invoice_id: str = ""
    advertiser_id: str = ""
    amount: float = 0.0
    due_date: str = ""
    
    def __post_init__(self):
        super().__post_init__()
        self.priority = EventPriority.NORMAL
        self.data.update({
            'invoice_id': self.invoice_id,
            'advertiser_id': self.advertiser_id,
            'amount': self.amount,
            'due_date': self.due_date
        })


# Event Handler Interface
class EventHandler(ABC):
    """Abstract base class for event handlers."""
    
    @abstractmethod
    def handle(self, event: Event) -> bool:
        """
        Handle the event.
        
        Args:
            event: Event to handle
            
        Returns:
            True if handled successfully
        """
        pass
    
    @property
    @abstractmethod
    def event_types(self) -> List[str]:
        """Get list of event types this handler can handle."""
        pass


# Concrete Event Handlers
class EmailNotificationHandler(EventHandler):
    """Handler for sending email notifications."""
    
    def __init__(self):
        self.email_service = EmailService()
    
    def handle(self, event: Event) -> bool:
        """Send email notification based on event type."""
        try:
            if isinstance(event, AdvertiserCreatedEvent):
                return self._send_welcome_email(event)
            elif isinstance(event, CampaignStatusChangedEvent):
                return self._send_campaign_status_email(event)
            elif isinstance(event, CreativeApprovedEvent):
                return self._send_creative_approval_email(event)
            elif isinstance(event, BudgetThresholdReachedEvent):
                return self._send_budget_alert_email(event)
            elif isinstance(event, PaymentProcessedEvent):
                return self._send_payment_confirmation_email(event)
            elif isinstance(event, InvoiceGeneratedEvent):
                return self._send_invoice_email(event)
            
            return True  # No email needed for this event type
            
        except Exception as e:
            logger.error(f"Email notification failed for event {event.event_id}: {str(e)}")
            return False
    
    @property
    def event_types(self) -> List[str]:
        """Get supported event types."""
        return [
            'AdvertiserCreatedEvent',
            'CampaignStatusChangedEvent',
            'CreativeApprovedEvent',
            'BudgetThresholdReachedEvent',
            'PaymentProcessedEvent',
            'InvoiceGeneratedEvent'
        ]
    
    def _send_welcome_email(self, event: AdvertiserCreatedEvent) -> bool:
        """Send welcome email to new advertiser."""
        # Implementation would use email service
        logger.info(f"Welcome email sent for advertiser {event.advertiser_id}")
        return True
    
    def _send_campaign_status_email(self, event: CampaignStatusChangedEvent) -> bool:
        """Send campaign status change email."""
        # Implementation would use email service
        logger.info(f"Campaign status email sent for campaign {event.campaign_id}")
        return True
    
    def _send_creative_approval_email(self, event: CreativeApprovedEvent) -> bool:
        """Send creative approval email."""
        # Implementation would use email service
        logger.info(f"Creative approval email sent for creative {event.creative_id}")
        return True
    
    def _send_budget_alert_email(self, event: BudgetThresholdReachedEvent) -> bool:
        """Send budget alert email."""
        # Implementation would use email service
        logger.info(f"Budget alert email sent for campaign {event.campaign_id}")
        return True
    
    def _send_payment_confirmation_email(self, event: PaymentProcessedEvent) -> bool:
        """Send payment confirmation email."""
        # Implementation would use email service
        logger.info(f"Payment confirmation email sent for transaction {event.transaction_id}")
        return True
    
    def _send_invoice_email(self, event: InvoiceGeneratedEvent) -> bool:
        """Send invoice email."""
        # Implementation would use email service
        logger.info(f"Invoice email sent for invoice {event.invoice_id}")
        return True


class AnalyticsEventHandler(EventHandler):
    """Handler for analytics-related events."""
    
    def __init__(self):
        self.analytics_service = AnalyticsService()
    
    def handle(self, event: Event) -> bool:
        """Update analytics based on event."""
        try:
            if isinstance(event, CampaignCreatedEvent):
                return self._track_campaign_creation(event)
            elif isinstance(event, CreativeUploadedEvent):
                return self._track_creative_upload(event)
            elif isinstance(event, CampaignStatusChangedEvent):
                return self._track_campaign_status_change(event)
            
            return True
            
        except Exception as e:
            logger.error(f"Analytics tracking failed for event {event.event_id}: {str(e)}")
            return False
    
    @property
    def event_types(self) -> List[str]:
        """Get supported event types."""
        return [
            'CampaignCreatedEvent',
            'CreativeUploadedEvent',
            'CampaignStatusChangedEvent'
        ]
    
    def _track_campaign_creation(self, event: CampaignCreatedEvent) -> bool:
        """Track campaign creation in analytics."""
        # Implementation would update analytics data
        logger.info(f"Campaign creation tracked for {event.campaign_id}")
        return True
    
    def _track_creative_upload(self, event: CreativeUploadedEvent) -> bool:
        """Track creative upload in analytics."""
        # Implementation would update analytics data
        logger.info(f"Creative upload tracked for {event.creative_id}")
        return True
    
    def _track_campaign_status_change(self, event: CampaignStatusChangedEvent) -> bool:
        """Track campaign status change in analytics."""
        # Implementation would update analytics data
        logger.info(f"Campaign status change tracked for {event.campaign_id}")
        return True


class FraudDetectionEventHandler(EventHandler):
    """Handler for fraud detection events."""
    
    def __init__(self):
        self.fraud_service = FraudDetectionService()
    
    def handle(self, event: Event) -> bool:
        """Handle fraud detection events."""
        try:
            if isinstance(event, FraudDetectedEvent):
                return self._handle_fraud_detection(event)
            
            return True
            
        except Exception as e:
            logger.error(f"Fraud detection handling failed for event {event.event_id}: {str(e)}")
            return False
    
    @property
    def event_types(self) -> List[str]:
        """Get supported event types."""
        return ['FraudDetectedEvent']
    
    def _handle_fraud_detection(self, event: FraudDetectedEvent) -> bool:
        """Handle fraud detection event."""
        # Block high-risk activities
        if event.risk_score >= 90:
            self.fraud_service.block_ip_address(event.ip_address)
            logger.warning(f"IP {event.ip_address} blocked due to high fraud risk")
        
        # Send alerts to administrators
        self.fraud_service.send_admin_alert(event)
        
        return True


class CacheInvalidationHandler(EventHandler):
    """Handler for cache invalidation events."""
    
    def __init__(self):
        self.cache_manager = CacheManager()
    
    def handle(self, event: Event) -> bool:
        """Invalidate cache based on event."""
        try:
            if isinstance(event, CampaignStatusChangedEvent):
                self.cache_manager.delete(f"campaign_performance:{event.campaign_id}")
            elif isinstance(event, CreativeApprovedEvent):
                self.cache_manager.delete(f"creative_performance:{event.creative_id}")
            elif isinstance(event, PaymentProcessedEvent):
                self.cache_manager.delete(f"billing_summary:{event.advertiser_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Cache invalidation failed for event {event.event_id}: {str(e)}")
            return False
    
    @property
    def event_types(self) -> List[str]:
        """Get supported event types."""
        return [
            'CampaignStatusChangedEvent',
            'CreativeApprovedEvent',
            'PaymentProcessedEvent'
        ]


class EventPublisher:
    """Event publisher for raising domain events."""
    
    def __init__(self):
        self.handlers: Dict[str, List[EventHandler]] = {}
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default event handlers."""
        default_handlers = [
            EmailNotificationHandler(),
            AnalyticsEventHandler(),
            FraudDetectionEventHandler(),
            CacheInvalidationHandler()
        ]
        
        for handler in default_handlers:
            self.register_handler(handler)
    
    def register_handler(self, handler: EventHandler):
        """Register an event handler."""
        for event_type in handler.event_types:
            if event_type not in self.handlers:
                self.handlers[event_type] = []
            self.handlers[event_type].append(handler)
    
    def unregister_handler(self, handler: EventHandler):
        """Unregister an event handler."""
        for event_type in handler.event_types:
            if event_type in self.handlers:
                self.handlers[event_type] = [
                    h for h in self.handlers[event_type] if h != handler
                ]
    
    def publish(self, event: Event) -> bool:
        """
        Publish an event to all registered handlers.
        
        Args:
            event: Event to publish
            
        Returns:
            True if all handlers processed successfully
        """
        logger.info(f"Publishing event: {event.event_type} (ID: {event.event_id})")
        
        success = True
        handlers = self.handlers.get(event.event_type, [])
        
        if not handlers:
            logger.warning(f"No handlers registered for event type: {event.event_type}")
            return True
        
        for handler in handlers:
            try:
                handler_success = handler.handle(event)
                if not handler_success:
                    success = False
                    logger.error(f"Handler failed for event {event.event_id}")
                
            except Exception as e:
                success = False
                logger.error(f"Handler exception for event {event.event_id}: {str(e)}")
        
        event.status = EventStatus.COMPLETED if success else EventStatus.FAILED
        logger.info(f"Event {event.event_id} processed with status: {event.status.value}")
        
        return success
    
    def publish_async(self, event: Event):
        """Publish event asynchronously."""
        from .tasks import process_domain_event
        process_domain_event.delay(event.to_dict())


class EventStore:
    """Event store for persisting and retrieving events."""
    
    def __init__(self):
        self.events: List[Event] = []
    
    def save_event(self, event: Event) -> bool:
        """Save event to store."""
        try:
            # In a real implementation, this would save to database
            self.events.append(event)
            logger.info(f"Event {event.event_id} saved to store")
            return True
        except Exception as e:
            logger.error(f"Failed to save event {event.event_id}: {str(e)}")
            return False
    
    def get_events(self, event_type: Optional[str] = None, 
                  start_date: Optional[datetime] = None,
                  end_date: Optional[datetime] = None,
                  limit: Optional[int] = None) -> List[Event]:
        """Get events from store with optional filtering."""
        filtered_events = self.events
        
        if event_type:
            filtered_events = [e for e in filtered_events if e.event_type == event_type]
        
        if start_date:
            filtered_events = [e for e in filtered_events if e.timestamp >= start_date]
        
        if end_date:
            filtered_events = [e for e in filtered_events if e.timestamp <= end_date]
        
        # Sort by timestamp descending
        filtered_events.sort(key=lambda e: e.timestamp, reverse=True)
        
        if limit:
            filtered_events = filtered_events[:limit]
        
        return filtered_events
    
    def get_event(self, event_id: str) -> Optional[Event]:
        """Get specific event by ID."""
        for event in self.events:
            if event.event_id == event_id:
                return event
        return None


class EventProcessor:
    """Event processor for handling async event processing."""
    
    def __init__(self, publisher: EventPublisher, store: EventStore):
        self.publisher = publisher
        self.store = store
    
    def process_event(self, event_data: Dict[str, Any]) -> bool:
        """Process event from data dictionary."""
        try:
            # Reconstruct event
            event = Event.from_dict(event_data)
            
            # Save to store
            self.store.save_event(event)
            
            # Process if ready
            if event.status == EventStatus.PENDING:
                if not event.delay_until or event.delay_until <= timezone.now():
                    return self.publisher.publish(event)
                else:
                    # Event is delayed, will be processed later
                    logger.info(f"Event {event.event_id} delayed until {event.delay_until}")
                    return True
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to process event {event_data.get('event_id')}: {str(e)}")
            return False
    
    def process_pending_events(self) -> int:
        """Process all pending events that are ready."""
        processed_count = 0
        
        for event in self.store.get_events():
            if (event.status == EventStatus.PENDING and 
                (not event.delay_until or event.delay_until <= timezone.now())):
                
                if self.publisher.publish(event):
                    processed_count += 1
        
        return processed_count


# Global instances
event_publisher = EventPublisher()
event_store = EventStore()
event_processor = EventProcessor(event_publisher, event_store)


# Convenience functions
def publish_event(event: Event, async: bool = False) -> bool:
    """
    Publish an event.
    
    Args:
        event: Event to publish
        async: Whether to publish asynchronously
        
    Returns:
        True if published successfully
    """
    # Save to store first
    event_store.save_event(event)
    
    if async:
        return event_publisher.publish_async(event)
    else:
        return event_publisher.publish(event)


def register_event_handler(handler: EventHandler):
    """Register an event handler."""
    event_publisher.register_handler(handler)


def unregister_event_handler(handler: EventHandler):
    """Unregister an event handler."""
    event_publisher.unregister_handler(handler)


# Domain event factory functions
def create_advertiser_created_event(advertiser_id: str, company_name: str, 
                                  contact_email: str) -> AdvertiserCreatedEvent:
    """Create advertiser created event."""
    return AdvertiserCreatedEvent(
        advertiser_id=advertiser_id,
        company_name=company_name,
        contact_email=contact_email
    )


def create_campaign_status_changed_event(campaign_id: str, advertiser_id: str,
                                       old_status: str, new_status: str,
                                       changed_by: str) -> CampaignStatusChangedEvent:
    """Create campaign status changed event."""
    return CampaignStatusChangedEvent(
        campaign_id=campaign_id,
        advertiser_id=advertiser_id,
        old_status=old_status,
        new_status=new_status,
        changed_by=changed_by
    )


def create_budget_threshold_reached_event(campaign_id: str, advertiser_id: str,
                                        threshold: int, current_utilization: float) -> BudgetThresholdReachedEvent:
    """Create budget threshold reached event."""
    return BudgetThresholdReachedEvent(
        campaign_id=campaign_id,
        advertiser_id=advertiser_id,
        threshold=threshold,
        current_utilization=current_utilization
    )


def create_fraud_detected_event(fraud_type: str, risk_score: int,
                               ip_address: str, user_agent: str) -> FraudDetectedEvent:
    """Create fraud detected event."""
    return FraudDetectedEvent(
        fraud_type=fraud_type,
        risk_score=risk_score,
        ip_address=ip_address,
        user_agent=user_agent
    )
