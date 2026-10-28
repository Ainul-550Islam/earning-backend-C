"""
Integration Signals — Django signals for integration system events.

This module provides signal definitions for integration system events
including connection status changes, data synchronization, and system health.
"""

from __future__ import annotations

import logging
from django.dispatch import Signal
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection Signals
# ---------------------------------------------------------------------------

# Fired when an integration connection is established
# kwargs: integration_id (str), integration_type (str), connection_info (dict)
integration_connected = Signal()

# Fired when an integration connection is lost
# kwargs: integration_id (str), integration_type (str), error (Exception), connection_info (dict)
integration_disconnected = Signal()

# Fired when an integration connection attempt fails
# kwargs: integration_id (str), integration_type (str), error (Exception), attempt_count (int)
integration_connection_failed = Signal()

# Fired when an integration connection is retried
# kwargs: integration_id (str), integration_type (str), attempt_count (int), max_attempts (int)
integration_connection_retry = Signal()


# ---------------------------------------------------------------------------
# Data Processing Signals
# ---------------------------------------------------------------------------

# Fired when data is received from an integration
# kwargs: integration_id (str), data (dict), data_type (str), timestamp (datetime)
data_received = Signal()

# Fired when data is sent to an integration
# kwargs: integration_id (str), data (dict), data_type (str), timestamp (datetime)
data_sent = Signal()

# Fired when data transformation is required
# kwargs: integration_id (str), source_data (dict), target_format (str), context (dict)
data_transform_required = Signal()

# Fired when data validation fails
# kwargs: integration_id (str), data (dict), validation_errors (list), context (dict)
data_validation_failed = Signal()

# Fired when data synchronization starts
# kwargs: integration_id (str), sync_type (str), sync_scope (dict), timestamp (datetime)
sync_started = Signal()

# Fired when data synchronization completes
# kwargs: integration_id (str), sync_type (str), sync_scope (dict), result (dict), timestamp (datetime)
sync_completed = Signal()

# Fired when data synchronization fails
# kwargs: integration_id (str), sync_type (str), sync_scope (dict), error (Exception), timestamp (datetime)
sync_failed = Signal()


# ---------------------------------------------------------------------------
# Circuit Breaker Signals
# ---------------------------------------------------------------------------

# Fired when circuit breaker opens
# kwargs: service_name (str), failure_count (int), threshold (int), timestamp (datetime)
circuit_breaker_opened = Signal()

# Fired when circuit breaker closes
# kwargs: service_name (str), success_count (int), timestamp (datetime)
circuit_breaker_closed = Signal()

# Fired when circuit breaker transitions to half-open
# kwargs: service_name (str), timestamp (datetime)
circuit_breaker_half_open = Signal()

# Fired when circuit breaker blocks a request
# kwargs: service_name (str), request_id (str), timestamp (datetime)
circuit_breaker_blocked = Signal()


# ---------------------------------------------------------------------------
# Queue Signals
# ---------------------------------------------------------------------------

# Fired when a message is queued
# kwargs: queue_name (str), message_id (str), message_type (str), priority (int), timestamp (datetime)
message_queued = Signal()

# Fired when a message is dequeued
# kwargs: queue_name (str), message_id (str), message_type (str), timestamp (datetime)
message_dequeued = Signal()

# Fired when a queue becomes full
# kwargs: queue_name (str), current_size (int), max_size (int), timestamp (datetime)
queue_full = Signal()

# Fired when a queue becomes empty
# kwargs: queue_name (str), timestamp (datetime)
queue_empty = Signal()

# Fired when message processing fails
# kwargs: queue_name (str), message_id (str), error (Exception), retry_count (int), timestamp (datetime)
message_processing_failed = Signal()


# ---------------------------------------------------------------------------
# Health and Monitoring Signals
# ---------------------------------------------------------------------------

# Fired when health check starts
# kwargs: integration_id (str), check_type (str), timestamp (datetime)
health_check_started = Signal()

# Fired when health check passes
# kwargs: integration_id (str), check_type (str), metrics (dict), timestamp (datetime)
health_check_passed = Signal()

# Fired when health check fails
# kwargs: integration_id (str), check_type (str), error (Exception), metrics (dict), timestamp (datetime)
health_check_failed = Signal()

# Fired when performance threshold is exceeded
# kwargs: integration_id (str), metric_name (str), current_value (float), threshold (float), timestamp (datetime)
performance_threshold_exceeded = Signal()

# Fired when performance returns to normal
# kwargs: integration_id (str), metric_name (str), current_value (float), threshold (float), timestamp (datetime)
performance_normal = Signal()


# ---------------------------------------------------------------------------
# Authentication and Authorization Signals
# ---------------------------------------------------------------------------

# Fired when authentication succeeds
# kwargs: integration_id (str), auth_type (str), user_id (str), timestamp (datetime)
authentication_succeeded = Signal()

# Fired when authentication fails
# kwargs: integration_id (str), auth_type (str), error (Exception), timestamp (datetime)
authentication_failed = Signal()

# Fired when authorization check succeeds
# kwargs: integration_id (str), user_id (str), permission (str), resource (str), timestamp (datetime)
authorization_succeeded = Signal()

# Fired when authorization check fails
# kwargs: integration_id (str), user_id (str), permission (str), resource (str), error (Exception), timestamp (datetime)
authorization_failed = Signal()


# ---------------------------------------------------------------------------
# Version Management Signals
# ---------------------------------------------------------------------------

# Fired when version compatibility check is performed
# kwargs: integration_id (str), current_version (str), required_version (str), is_compatible (bool), timestamp (datetime)
version_compatibility_checked = Signal()

# Fired when version upgrade is available
# kwargs: integration_id (str), current_version (str), available_version (str), upgrade_info (dict), timestamp (datetime)
version_upgrade_available = Signal()

# Fired when version upgrade is performed
# kwargs: integration_id (str), old_version (str), new_version (str), upgrade_result (dict), timestamp (datetime)
version_upgraded = Signal()

# Fired when version downgrade is performed
# kwargs: integration_id (str), old_version (str), new_version (str), downgrade_result (dict), timestamp (datetime)
version_downgraded = Signal()


# ---------------------------------------------------------------------------
# Webhook Signals
# ---------------------------------------------------------------------------

# Fired when webhook is received
# kwargs: webhook_id (str), integration_id (str), event_type (str), payload (dict), headers (dict), timestamp (datetime)
webhook_received = Signal()

# Fired when webhook is processed
# kwargs: webhook_id (str), integration_id (str), event_type (str), processing_result (dict), timestamp (datetime)
webhook_processed = Signal()

# Fired when webhook processing fails
# kwargs: webhook_id (str), integration_id (str), event_type (str), error (Exception), timestamp (datetime)
webhook_processing_failed = Signal()

# Fired when webhook is delivered
# kwargs: webhook_id (str), integration_id (str), target_url (str), delivery_result (dict), timestamp (datetime)
webhook_delivered = Signal()

# Fired when webhook delivery fails
# kwargs: webhook_id (str), integration_id (str), target_url (str), error (Exception), timestamp (datetime)
webhook_delivery_failed = Signal()


# ---------------------------------------------------------------------------
# Configuration Signals
# ---------------------------------------------------------------------------

# Fired when integration configuration is updated
# kwargs: integration_id (str), old_config (dict), new_config (dict), updated_fields (list), timestamp (datetime)
configuration_updated = Signal()

# Fired when integration configuration is validated
# kwargs: integration_id (str), config (dict), validation_result (dict), timestamp (datetime)
configuration_validated = Signal()

# Fired when integration configuration validation fails
# kwargs: integration_id (str), config (dict), validation_errors (list), timestamp (datetime)
configuration_validation_failed = Signal()

# Fired when integration is enabled
# kwargs: integration_id (str), enabled_by (str), reason (str), timestamp (datetime)
integration_enabled = Signal()

# Fired when integration is disabled
# kwargs: integration_id (str), disabled_by (str), reason (str), timestamp (datetime)
integration_disabled = Signal()


# ---------------------------------------------------------------------------
# Error and Recovery Signals
# ---------------------------------------------------------------------------

# Fired when an error occurs in integration processing
# kwargs: integration_id (str), error_type (str), error (Exception), context (dict), timestamp (datetime)
integration_error = Signal()

# Fired when error recovery is attempted
# kwargs: integration_id (str), error (Exception), recovery_strategy (str), timestamp (datetime)
error_recovery_attempted = Signal()

# Fired when error recovery succeeds
# kwargs: integration_id (str), error (Exception), recovery_strategy (str), recovery_result (dict), timestamp (datetime)
error_recovery_succeeded = Signal()

# Fired when error recovery fails
# kwargs: integration_id (str), error (Exception), recovery_strategy (str), recovery_error (Exception), timestamp (datetime)
error_recovery_failed = Signal()

# Fired when fallback logic is triggered
# kwargs: integration_id (str), operation (str), fallback_reason (str), fallback_result (dict), timestamp (datetime)
fallback_triggered = Signal()


# ---------------------------------------------------------------------------
# Audit and Logging Signals
# ---------------------------------------------------------------------------

# Fired when audit log entry is created
# kwargs: integration_id (str), action (str), resource (str), user_id (str), changes (dict), timestamp (datetime)
audit_log_created = Signal()

# Fired when security event occurs
# kwargs: integration_id (str), event_type (str), severity (str), details (dict), user_id (str), timestamp (datetime)
security_event = Signal()

# Fired when compliance check is performed
# kwargs: integration_id (str), compliance_type (str), check_result (dict), violations (list), timestamp (datetime)
compliance_checked = Signal()

# Fired when compliance violation is detected
# kwargs: integration_id (str), compliance_type (str), violation (dict), severity (str), timestamp (datetime)
compliance_violation = Signal()


# ---------------------------------------------------------------------------
# Batch Processing Signals
# ---------------------------------------------------------------------------

# Fired when batch processing starts
# kwargs: integration_id (str), batch_id (str), batch_size (int), processing_type (str), timestamp (datetime)
batch_processing_started = Signal()

# Fired when batch processing completes
# kwargs: integration_id (str), batch_id (str), processing_result (dict), timestamp (datetime)
batch_processing_completed = Signal()

# Fired when batch item is processed
# kwargs: integration_id (str), batch_id (str), item_id (str), item_result (dict), timestamp (datetime)
batch_item_processed = Signal()

# Fired when batch processing fails
# kwargs: integration_id (str), batch_id (str), error (Exception), failed_items (list), timestamp (datetime)
batch_processing_failed = Signal()


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def send_integration_signal(
    signal: Signal,
    sender: Any = None,
    **kwargs: Any
) -> None:
    """Send an integration signal with error handling."""
    try:
        signal.send(sender=sender, **kwargs)
        logger.debug(f"Signal sent: {signal.__name__} with kwargs: {list(kwargs.keys())}")
    except Exception as e:
        logger.error(f"Error sending signal {signal.__name__}: {e}")


def create_signal_context(
    integration_id: str,
    **additional_context: Any
) -> Dict[str, Any]:
    """Create standardized signal context."""
    from datetime import datetime
    
    context = {
        "integration_id": integration_id,
        "timestamp": datetime.utcnow()
    }
    context.update(additional_context)
    return context


# Initialize logging
logger.info("Integration signals module initialized")
