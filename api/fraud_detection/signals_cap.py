# =============================================================================
# fraud_detection/signals_cap.py
# =============================================================================
"""
Capital Signals for Fraud Detection System.

Provides capital-level signals for major fraud events,
regulatory reporting, and system-wide notifications.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django.utils import timezone
from django.contrib.auth import get_user_model

from api.fraud_detection.exceptions import FraudDetectionError


logger = logging.getLogger(__name__)

User = get_user_model()


@dataclass
class CapitalEvent:
    """Data class for capital-level fraud events."""
    event_type: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    description: str
    affected_entities: List[str]
    financial_impact: Optional[float] = None
    regulatory_impact: bool = False
    requires_immediate_action: bool = False
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()


class CapitalSignalManager:
    """
    Manager for capital-level fraud signals.
    
    Handles major fraud events that require
    executive attention and regulatory reporting.
    """
    
    def __init__(self):
        """Initialize capital signal manager."""
        self.signals = self._register_capital_signals()
        self.subscribers = {}
        self.event_history = []
        self.max_history = 1000
    
    def _register_capital_signals(self) -> Dict[str, Signal]:
        """Register capital-level signals."""
        return {
            'major_fraud_detected': Signal(),
            'regulatory_breach': Signal(),
            'financial_loss_threshold': Signal(),
            'system_compromise': Signal(),
            'executive_alert': Signal(),
            'compliance_failure': Signal(),
            'data_breach': Signal(),
            'money_laundering_detected': Signal(),
            'terrorist_financing_detected': Signal(),
            'critical_system_failure': Signal(),
        }
    
    def send_capital_signal(self, signal_name: str, event: CapitalEvent):
        """
        Send capital-level signal.
        
        Args:
            signal_name: Name of the signal
            event: Capital event data
        """
        try:
            if signal_name not in self.signals:
                raise FraudDetectionError(f"Unknown capital signal: {signal_name}")
            
            # Add to history
            self.event_history.append({
                'signal_name': signal_name,
                'event': event,
                'sent_at': timezone.now()
            })
            
            # Trim history if needed
            if len(self.event_history) > self.max_history:
                self.event_history = self.event_history[-self.max_history:]
            
            # Send signal
            self.signals[signal_name].send(sender=self.__class__, event=event)
            
            # Log capital event
            self._log_capital_event(signal_name, event)
            
            logger.critical(f"Capital signal sent: {signal_name} - {event.description}")
            
        except Exception as e:
            logger.error(f"Error sending capital signal {signal_name}: {e}")
    
    def _log_capital_event(self, signal_name: str, event: CapitalEvent):
        """Log capital event for audit trail."""
        log_data = {
            'signal_name': signal_name,
            'event_type': event.event_type,
            'severity': event.severity,
            'description': event.description,
            'affected_entities': event.affected_entities,
            'financial_impact': event.financial_impact,
            'regulatory_impact': event.regulatory_impact,
            'requires_immediate_action': event.requires_immediate_action,
            'timestamp': event.timestamp.isoformat(),
            'metadata': event.metadata
        }
        
        logger.critical(f"CAPITAL EVENT: {log_data}")
    
    def subscribe_to_capital_signals(self, subscriber_func, signal_names: List[str] = None):
        """
        Subscribe to capital signals.
        
        Args:
            subscriber_func: Function to handle signals
            signal_names: List of signal names (None for all)
        """
        if signal_names is None:
            signal_names = list(self.signals.keys())
        
        for signal_name in signal_names:
            if signal_name in self.signals:
                self.signals[signal_name].connect(subscriber_func)
                
                if signal_name not in self.subscribers:
                    self.subscribers[signal_name] = []
                self.subscribers[signal_name].append(subscriber_func)
                
                logger.info(f"Subscribed to capital signal: {signal_name}")
    
    def get_capital_event_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get capital event history.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of capital events
        """
        return self.event_history[-limit:] if self.event_history else []
    
    def get_active_capital_alerts(self) -> List[Dict[str, Any]]:
        """
        Get active capital alerts requiring action.
        
        Returns:
            List of active alerts
        """
        active_alerts = []
        
        for event_record in self.event_history:
            event = event_record['event']
            if event.requires_immediate_action:
                active_alerts.append({
                    'signal_name': event_record['signal_name'],
                    'event': event,
                    'sent_at': event_record['sent_at']
                })
        
        return active_alerts


# Global capital signal manager
capital_signal_manager = CapitalSignalManager()


# Capital signal receivers
@receiver(capital_signal_manager.signals['major_fraud_detected'])
def major_fraud_detected_receiver(sender, event: CapitalEvent, **kwargs):
    """Receiver for major fraud detection signals."""
    try:
        logger.critical(f"MAJOR FRAUD DETECTED: {event.description}")
        
        # Send executive notifications
        from api.fraud_detection.notifications_push import send_system_alert
        send_system_alert({
            'alert_type': 'major_fraud',
            'message': f"Major fraud detected: {event.description}",
            'severity': event.severity,
            'affected_entities': event.affected_entities,
            'financial_impact': event.financial_impact,
            'requires_immediate_action': event.requires_immediate_action
        }, priority='critical')
        
        # Create executive fraud case
        from api.fraud_detection.services import fraud_detection_service
        fraud_detection_service.create_fraud_case(
            user_id=event.affected_entities[0] if event.affected_entities else None,
            case_data={
                'case_type': 'major_fraud',
                'risk_score': 95,
                'description': event.description,
                'severity': 'critical',
                'detection_method': 'capital_signal',
                'evidence': event.metadata
            },
            auto_assign=True
        )
        
        # Record capital metric
        record_fraud_metric('major_fraud_detected', 1, {
            'event_type': event.event_type,
            'severity': event.severity,
            'financial_impact': event.financial_impact,
            'affected_entities': len(event.affected_entities)
        })
        
    except Exception as e:
        logger.error(f"Error in major fraud detection receiver: {e}")


@receiver(capital_signal_manager.signals['regulatory_breach'])
def regulatory_breach_receiver(sender, event: CapitalEvent, **kwargs):
    """Receiver for regulatory breach signals."""
    try:
        logger.critical(f"REGULATORY BREACH: {event.description}")
        
        # Send compliance notifications
        from api.fraud_detection.notifications_push import send_system_alert
        send_system_alert({
            'alert_type': 'regulatory_breach',
            'message': f"Regulatory breach detected: {event.description}",
            'severity': event.severity,
            'affected_entities': event.affected_entities,
            'regulatory_impact': True,
            'requires_immediate_action': True
        }, priority='critical')
        
        # Generate compliance report
        from api.fraud_detection.services import compliance_service
        compliance_service.generate_compliance_report(
            report_type='regulatory_breach',
            period_days=1
        )
        
        # Record capital metric
        record_fraud_metric('regulatory_breach', 1, {
            'event_type': event.event_type,
            'severity': event.severity,
            'affected_entities': len(event.affected_entities)
        })
        
    except Exception as e:
        logger.error(f"Error in regulatory breach receiver: {e}")


@receiver(capital_signal_manager.signals['financial_loss_threshold'])
def financial_loss_threshold_receiver(sender, event: CapitalEvent, **kwargs):
    """Receiver for financial loss threshold signals."""
    try:
        logger.critical(f"FINANCIAL LOSS THRESHOLD EXCEEDED: {event.description}")
        
        # Send financial alert
        from api.fraud_detection.notifications_push import send_system_alert
        send_system_alert({
            'alert_type': 'financial_loss',
            'message': f"Financial loss threshold exceeded: {event.description}",
            'severity': event.severity,
            'financial_impact': event.financial_impact,
            'affected_entities': event.affected_entities,
            'requires_immediate_action': True
        }, priority='critical')
        
        # Create high-priority case
        from api.fraud_detection.services import fraud_detection_service
        fraud_detection_service.create_fraud_case(
            user_id=event.affected_entities[0] if event.affected_entities else None,
            case_data={
                'case_type': 'financial_loss',
                'risk_score': 90,
                'description': event.description,
                'severity': 'critical',
                'detection_method': 'capital_signal',
                'evidence': {
                    'financial_impact': event.financial_impact,
                    'metadata': event.metadata
                }
            },
            auto_assign=True
        )
        
        # Record capital metric
        record_fraud_metric('financial_loss_threshold', 1, {
            'financial_impact': event.financial_impact,
            'affected_entities': len(event.affected_entities)
        })
        
    except Exception as e:
        logger.error(f"Error in financial loss threshold receiver: {e}")


@receiver(capital_signal_manager.signals['money_laundering_detected'])
def money_laundering_detected_receiver(sender, event: CapitalEvent, **kwargs):
    """Receiver for money laundering detection signals."""
    try:
        logger.critical(f"MONEY LAUNDERING DETECTED: {event.description}")
        
        # Send AML alert
        from api.fraud_detection.notifications_push import send_system_alert
        send_system_alert({
            'alert_type': 'money_laundering',
            'message': f"Money laundering detected: {event.description}",
            'severity': event.severity,
            'affected_entities': event.affected_entities,
            'regulatory_impact': True,
            'requires_immediate_action': True
        }, priority='critical')
        
        # File SAR immediately
        from api.fraud_detection.services import compliance_service
        compliance_service.file_sar_report(
            case_id=event.metadata.get('case_id', 'unknown'),
            sar_data={
                'suspicious_activity': event.description,
                'financial_amount': event.financial_impact,
                'entities_involved': event.affected_entities,
                'detection_method': 'capital_signal',
                'urgency': 'high'
            }
        )
        
        # Record capital metric
        record_fraud_metric('money_laundering_detected', 1, {
            'event_type': event.event_type,
            'severity': event.severity,
            'financial_impact': event.financial_impact
        })
        
    except Exception as e:
        logger.error(f"Error in money laundering detected receiver: {e}")


@receiver(capital_signal_manager.signals['terrorist_financing_detected'])
def terrorist_financing_detected_receiver(sender, event: CapitalEvent, **kwargs):
    """Receiver for terrorist financing detection signals."""
    try:
        logger.critical(f"TERRORIST FINANCING DETECTED: {event.description}")
        
        # Send highest priority alert
        from api.fraud_detection.notifications_push import send_system_alert
        send_system_alert({
            'alert_type': 'terrorist_financing',
            'message': f"Terrorist financing detected: {event.description}",
            'severity': 'CRITICAL',
            'affected_entities': event.affected_entities,
            'regulatory_impact': True,
            'requires_immediate_action': True
        }, priority='critical')
        
        # Immediate regulatory reporting
        from api.fraud_detection.services import compliance_service
        compliance_service.generate_compliance_report(
            report_type='terrorist_financing',
            period_days=1
        )
        
        # Record capital metric
        record_fraud_metric('terrorist_financing_detected', 1, {
            'event_type': event.event_type,
            'severity': event.severity,
            'affected_entities': len(event.affected_entities)
        })
        
    except Exception as e:
        logger.error(f"Error in terrorist financing detected receiver: {e}")


# Capital signal convenience functions
def send_major_fraud_signal(description: str, affected_entities: List[str],
                           financial_impact: Optional[float] = None,
                           metadata: Optional[Dict[str, Any]] = None):
    """Send major fraud detection signal."""
    event = CapitalEvent(
        event_type='major_fraud',
        severity='CRITICAL',
        description=description,
        affected_entities=affected_entities,
        financial_impact=financial_impact,
        regulatory_impact=True,
        requires_immediate_action=True,
        metadata=metadata
    )
    
    capital_signal_manager.send_capital_signal('major_fraud_detected', event)


def send_regulatory_breach_signal(description: str, affected_entities: List[str],
                                  regulatory_impact: bool = True,
                                  metadata: Optional[Dict[str, Any]] = None):
    """Send regulatory breach signal."""
    event = CapitalEvent(
        event_type='regulatory_breach',
        severity='CRITICAL',
        description=description,
        affected_entities=affected_entities,
        regulatory_impact=regulatory_impact,
        requires_immediate_action=True,
        metadata=metadata
    )
    
    capital_signal_manager.send_capital_signal('regulatory_breach', event)


def send_financial_loss_signal(description: str, affected_entities: List[str],
                               financial_impact: float,
                               metadata: Optional[Dict[str, Any]] = None):
    """Send financial loss threshold signal."""
    event = CapitalEvent(
        event_type='financial_loss',
        severity='HIGH',
        description=description,
        affected_entities=affected_entities,
        financial_impact=financial_impact,
        requires_immediate_action=True,
        metadata=metadata
    )
    
    capital_signal_manager.send_capital_signal('financial_loss_threshold', event)


def send_money_laundering_signal(description: str, affected_entities: List[str],
                                  financial_impact: Optional[float] = None,
                                  metadata: Optional[Dict[str, Any]] = None):
    """Send money laundering detection signal."""
    event = CapitalEvent(
        event_type='money_laundering',
        severity='CRITICAL',
        description=description,
        affected_entities=affected_entities,
        financial_impact=financial_impact,
        regulatory_impact=True,
        requires_immediate_action=True,
        metadata=metadata
    )
    
    capital_signal_manager.send_capital_signal('money_laundering_detected', event)


def send_terrorist_financing_signal(description: str, affected_entities: List[str],
                                     financial_impact: Optional[float] = None,
                                     metadata: Optional[Dict[str, Any]] = None):
    """Send terrorist financing detection signal."""
    event = CapitalEvent(
        event_type='terrorist_financing',
        severity='CRITICAL',
        description=description,
        affected_entities=affected_entities,
        financial_impact=financial_impact,
        regulatory_impact=True,
        requires_immediate_action=True,
        metadata=metadata
    )
    
    capital_signal_manager.send_capital_signal('terrorist_financing_detected', event)


# Capital signal monitoring
def get_active_capital_alerts() -> List[Dict[str, Any]]:
    """Get active capital alerts requiring action."""
    return capital_signal_manager.get_active_capital_alerts()


def get_capital_event_summary(hours: int = 24) -> Dict[str, Any]:
    """Get summary of capital events."""
    history = capital_signal_manager.get_capital_event_history(limit=1000)
    
    cutoff_time = timezone.now() - timedelta(hours=hours)
    recent_events = [
        event for event in history
        if event['sent_at'] >= cutoff_time
    ]
    
    # Count by severity
    severity_counts = {}
    for event in recent_events:
        severity = event['event'].severity
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
    
    # Count by type
    type_counts = {}
    for event in recent_events:
        event_type = event['event'].event_type
        type_counts[event_type] = type_counts.get(event_type, 0) + 1
    
    return {
        'period_hours': hours,
        'total_events': len(recent_events),
        'severity_distribution': severity_counts,
        'event_type_distribution': type_counts,
        'requires_action': len([
            event for event in recent_events
            if event['event'].requires_immediate_action
        ]),
        'regulatory_impact': len([
            event for event in recent_events
            if event['event'].regulatory_impact
        ]),
        'total_financial_impact': sum(
            event['event'].financial_impact or 0
            for event in recent_events
        )
    }


def record_fraud_metric(metric_name: str, value: int, metadata: Dict[str, Any]):
    """Record fraud metric for capital events."""
    from api.fraud_detection.monitoring import record_fraud_metric as record_metric
    record_metric(metric_name, value, metadata)
