"""
Integration System Tests - Comprehensive Test Suite

Comprehensive test suite for the integration system covering all components
with unit tests, integration tests, and performance tests.
"""

import unittest
import asyncio
import json
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth.models import User

from .integ_constants import (
    IntegrationEvent, IntegrationStatus, IntegrationPriority,
    IntegrationProtocol, IntegrationDataType, ErrorSeverity
)
from .integ_handler import IntegrationHandler
from .integ_signals import SignalManager
from .integ_adapter import IntegrationAdapter, AdapterFactory
from .integ_registry import IntegrationRegistry
from .bridge import BridgeManager, create_synchronous_bridge
from .event_bus import EventBus, Event
from .transformer import DataTransformer
from .circuit_breaker import CircuitBreaker, CircuitBreakerManager
from .versioning import VersionManager
from .webhooks_integration import WebhookManager
from .data_bridge import DataBridge, SyncDirection, ConflictResolution
from .message_queue import MessageQueueManager, QueueType
from .data_validator import DataValidator, ValidationType
from .integ_exceptions import (
    IntegrationError, ValidationError, NetworkError,
    AuthenticationError, CircuitBreakerError
)
from .fallback_logic import FallbackManager, FallbackStrategy
from .auth_bridge import AuthBridge, PermissionType, ResourceType
from .performance_monitor import PerformanceMonitor
from .integ_audit_logs import AuditLogger, AuditLogLevel, AuditCategory
from .health_check import HealthChecker, HealthStatus
from .sync_manager import SyncManager, ConflictType, ResolutionStrategy


class IntegrationConstantsTest(TestCase):
    """Test integration constants and enums."""
    
    def test_integration_events(self):
        """Test integration event enum."""
        self.assertEqual(IntegrationEvent.RATE_LIMIT_EXCEEDED.value, "rate_limit_exceeded")
        self.assertEqual(IntegrationEvent.ABUSE_DETECTED.value, "abuse_detected")
        self.assertEqual(IntegrationEvent.IP_BLOCKED.value, "ip_blocked")
        
        # Test all events have values
        for event in IntegrationEvent:
            self.assertIsNotNone(event.value)
            self.assertIsInstance(event.value, str)
    
    def test_integration_status(self):
        """Test integration status enum."""
        self.assertEqual(IntegrationStatus.SUCCESS.value, "success")
        self.assertEqual(IntegrationStatus.FAILED.value, "failed")
        self.assertEqual(IntegrationStatus.PENDING.value, "pending")
        
        # Test all statuses have values
        for status in IntegrationStatus:
            self.assertIsNotNone(status.value)
            self.assertIsInstance(status.value, str)
    
    def test_integration_priority(self):
        """Test integration priority enum."""
        self.assertEqual(IntegrationPriority.LOW.value, "low")
        self.assertEqual(IntegrationPriority.NORMAL.value, "normal")
        self.assertEqual(IntegrationPriority.HIGH.value, "high")
        self.assertEqual(IntegrationPriority.CRITICAL.value, "critical")
    
    def test_protocol_configurations(self):
        """Test protocol configurations."""
        from .integ_constants import PROTOCOL_CONFIG
        
        # Test HTTP protocol config
        http_config = PROTOCOL_CONFIG[IntegrationProtocol.HTTP]
        self.assertEqual(http_config["default_port"], 80)
        self.assertFalse(http_config["secure"])
        self.assertEqual(http_config["timeout"], 30)
        
        # Test HTTPS protocol config
        https_config = PROTOCOL_CONFIG[IntegrationProtocol.HTTPS]
        self.assertEqual(https_config["default_port"], 443)
        self.assertTrue(https_config["secure"])
        
        # Test all protocols have configs
        for protocol in IntegrationProtocol:
            self.assertIn(protocol, PROTOCOL_CONFIG)


class IntegrationHandlerTest(TestCase):
    """Test integration handler."""
    
    def setUp(self):
        self.handler = IntegrationHandler()
    
    def test_handler_initialization(self):
        """Test handler initialization."""
        self.assertIsNotNone(self.handler)
        self.assertIsNotNone(self.handler.middleware)
        self.assertIsNotNone(self.handler.event_handlers)
    
    def test_register_handler(self):
        """Test handler registration."""
        def test_handler(event_data):
            return {"processed": True}
        
        self.handler.register_handler(IntegrationEvent.RATE_LIMIT_EXCEEDED, test_handler)
        self.assertIn(IntegrationEvent.RATE_LIMIT_EXCEEDED, self.handler.event_handlers)
        self.assertEqual(len(self.handler.event_handlers[IntegrationEvent.RATE_LIMIT_EXCEEDED]), 1)
    
    def test_process_event(self):
        """Test event processing."""
        def test_handler(event_data):
            return {"processed": True}
        
        self.handler.register_handler(IntegrationEvent.RATE_LIMIT_EXCEEDED, test_handler)
        
        event_data = {
            "event_type": IntegrationEvent.RATE_LIMIT_EXCEEDED,
            "user_id": "test_user",
            "ip_address": "127.0.0.1"
        }
        
        result = self.handler.process_event(event_data)
        self.assertIsNotNone(result)
        self.assertTrue(result.get("processed", False))


class EventBusTest(TestCase):
    """Test event bus system."""
    
    def setUp(self):
        self.event_bus = EventBus()
    
    def test_event_bus_initialization(self):
        """Test event bus initialization."""
        self.assertIsNotNone(self.event_bus)
        self.assertIsNotNone(self.event_bus.subscriptions)
        self.assertIsNotNone(self.event_bus.event_history)
    
    def test_subscribe_publish(self):
        """Test event subscription and publishing."""
        received_events = []
        
        def test_handler(event):
            received_events.append(event)
        
        # Subscribe to event
        self.event_bus.subscribe("test_event", test_handler)
        
        # Publish event
        event = Event("test_event", {"message": "test"})
        asyncio.run(self.event_bus.publish(event))
        
        # Verify event was received
        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].event_type, "test_event")
        self.assertEqual(received_events[0].data["message"], "test")
    
    def test_event_filtering(self):
        """Test event filtering."""
        received_events = []
        
        def test_handler(event):
            received_events.append(event)
        
        # Subscribe with filter
        def filter_func(event):
            return event.data.get("priority") == "high"
        
        self.event_bus.subscribe("test_event", test_handler, filter_func)
        
        # Publish high priority event
        high_event = Event("test_event", {"message": "high", "priority": "high"})
        asyncio.run(self.event_bus.publish(high_event))
        
        # Publish low priority event
        low_event = Event("test_event", {"message": "low", "priority": "low"})
        asyncio.run(self.event_bus.publish(low_event))
        
        # Verify only high priority event was received
        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].data["priority"], "high")


class CircuitBreakerTest(TestCase):
    """Test circuit breaker functionality."""
    
    def setUp(self):
        self.circuit_breaker = CircuitBreaker("test_breaker", failure_threshold=3, recovery_timeout=60)
    
    def test_circuit_breaker_states(self):
        """Test circuit breaker state transitions."""
        # Initially closed
        self.assertEqual(self.circuit_breaker.get_state().value, "closed")
        
        # Simulate failures
        for i in range(3):
            self.circuit_breaker.record_failure()
        
        # Should be open now
        self.assertEqual(self.circuit_breaker.get_state().value, "open")
        
        # Wait for recovery timeout
        self.circuit_breaker.state_machine.state_timeout = time.time() - 1
        
        # Next call should transition to half-open
        self.circuit_breaker.record_success()
        self.assertEqual(self.circuit_breaker.get_state().value, "half_open")
    
    def test_circuit_breaker_protection(self):
        """Test circuit breaker protection."""
        # Test with closed circuit
        result = self.circuit_breaker.call(lambda: "success")
        self.assertEqual(result, "success")
        
        # Test with open circuit
        for i in range(3):
            self.circuit_breaker.record_failure()
        
        with self.assertRaises(CircuitBreakerError):
            self.circuit_breaker.call(lambda: "should_fail")


class DataTransformerTest(TestCase):
    """Test data transformer."""
    
    def setUp(self):
        self.transformer = DataTransformer()
    
    def test_field_mapping(self):
        """Test field mapping transformation."""
        source_data = {
            "old_name": "value1",
            "another_field": "value2"
        }
        
        mapping = {
            "old_name": "new_name",
            "another_field": "another_field"
        }
        
        result = self.transformer.transform_field_mapping(source_data, mapping)
        
        self.assertEqual(result["new_name"], "value1")
        self.assertEqual(result["another_field"], "value2")
        self.assertNotIn("old_name", result)
    
    def test_format_conversion(self):
        """Test format conversion."""
        # Test JSON to XML
        json_data = {"name": "test", "value": 123}
        xml_result = self.transformer.json_to_xml(json_data)
        self.assertIn("<name>test</name>", xml_result)
        self.assertIn("<value>123</value>", xml_result)
        
        # Test XML to JSON
        xml_data = "<root><name>test</name><value>123</value></root>"
        json_result = self.transformer.xml_to_json(xml_data)
        self.assertEqual(json_result["name"], "test")
        self.assertEqual(json_result["value"], "123")


class DataValidatorTest(TestCase):
    """Test data validator."""
    
    def setUp(self):
        self.validator = DataValidator()
    
    def test_required_validation(self):
        """Test required field validation."""
        schema = {
            "name": {"type": ValidationType.REQUIRED},
            "email": {"type": ValidationType.REQUIRED}
        }
        
        # Valid data
        valid_data = {"name": "test", "email": "test@example.com"}
        result = self.validator.validate(valid_data, schema)
        self.assertTrue(result.is_valid)
        
        # Invalid data
        invalid_data = {"name": "test"}  # Missing email
        result = self.validator.validate(invalid_data, schema)
        self.assertFalse(result.is_valid)
        self.assertIn("email", result.errors)
    
    def test_type_validation(self):
        """Test type validation."""
        schema = {
            "age": {"type": ValidationType.TYPE, "expected_type": int},
            "name": {"type": ValidationType.TYPE, "expected_type": str}
        }
        
        # Valid data
        valid_data = {"age": 25, "name": "test"}
        result = self.validator.validate(valid_data, schema)
        self.assertTrue(result.is_valid)
        
        # Invalid data
        invalid_data = {"age": "25", "name": "test"}  # age is string
        result = self.validator.validate(invalid_data, schema)
        self.assertFalse(result.is_valid)
        self.assertIn("age", result.errors)
    
    def test_range_validation(self):
        """Test range validation."""
        schema = {
            "age": {"type": ValidationType.RANGE, "min_value": 0, "max_value": 120}
        }
        
        # Valid data
        valid_data = {"age": 25}
        result = self.validator.validate(valid_data, schema)
        self.assertTrue(result.is_valid)
        
        # Invalid data (too high)
        invalid_data = {"age": 150}
        result = self.validator.validate(invalid_data, schema)
        self.assertFalse(result.is_valid)
        self.assertIn("age", result.errors)


class MessageQueueTest(TestCase):
    """Test message queue functionality."""
    
    def setUp(self):
        self.queue_manager = MessageQueueManager()
    
    def test_queue_creation(self):
        """Test queue creation."""
        queue = self.queue_manager.create_queue("test_queue", QueueType.PRIORITY)
        self.assertIsNotNone(queue)
        self.assertEqual(queue.name, "test_queue")
    
    def test_message_enqueue_dequeue(self):
        """Test message enqueue and dequeue."""
        queue = self.queue_manager.create_queue("test_queue", QueueType.FIFO)
        
        # Enqueue message
        message = {"id": 1, "content": "test message"}
        self.queue_manager.enqueue("test_queue", message)
        
        # Dequeue message
        dequeued = self.queue_manager.dequeue("test_queue")
        self.assertEqual(dequeued["id"], 1)
        self.assertEqual(dequeued["content"], "test message")
    
    def test_priority_queue(self):
        """Test priority queue ordering."""
        queue = self.queue_manager.create_queue("priority_queue", QueueType.PRIORITY)
        
        # Enqueue messages with different priorities
        low_msg = {"id": 1, "priority": 1}
        high_msg = {"id": 2, "priority": 10}
        medium_msg = {"id": 3, "priority": 5}
        
        self.queue_manager.enqueue("priority_queue", low_msg, priority=1)
        self.queue_manager.enqueue("priority_queue", high_msg, priority=10)
        self.queue_manager.enqueue("priority_queue", medium_msg, priority=5)
        
        # Dequeue should return in priority order
        first = self.queue_manager.dequeue("priority_queue")
        self.assertEqual(first["id"], 2)  # High priority
        
        second = self.queue_manager.dequeue("priority_queue")
        self.assertEqual(second["id"], 3)  # Medium priority
        
        third = self.queue_manager.dequeue("priority_queue")
        self.assertEqual(third["id"], 1)  # Low priority


class WebhookManagerTest(TestCase):
    """Test webhook manager."""
    
    def setUp(self):
        self.webhook_manager = WebhookManager()
    
    def test_webhook_registration(self):
        """Test webhook registration."""
        webhook_config = {
            "url": "https://example.com/webhook",
            "events": ["test_event"],
            "secret": "test_secret"
        }
        
        webhook_id = self.webhook_manager.register_webhook(webhook_config)
        self.assertIsNotNone(webhook_id)
        
        webhook = self.webhook_manager.get_webhook(webhook_id)
        self.assertEqual(webhook["url"], "https://example.com/webhook")
        self.assertEqual(webhook["events"], ["test_event"])
    
    @patch('requests.post')
    def test_webhook_delivery(self, mock_post):
        """Test webhook delivery."""
        mock_post.return_value.status_code = 200
        
        webhook_config = {
            "url": "https://example.com/webhook",
            "events": ["test_event"],
            "secret": "test_secret"
        }
        
        webhook_id = self.webhook_manager.register_webhook(webhook_config)
        
        # Deliver webhook
        event_data = {"event": "test_event", "data": "test"}
        result = self.webhook_manager.deliver_webhook(webhook_id, event_data)
        
        self.assertTrue(result.get("success", False))
        mock_post.assert_called_once()


class AuthBridgeTest(TestCase):
    """Test authentication bridge."""
    
    def setUp(self):
        self.auth_bridge = AuthBridge()
    
    def test_permission_granting(self):
        """Test permission granting."""
        user_id = "test_user"
        permission_name = "rate_limit.read"
        
        self.auth_bridge.grant_permission_to_user(user_id, permission_name)
        
        # Check permission
        has_permission = self.auth_bridge.check_permission(user_id, permission_name)
        self.assertTrue(has_permission)
    
    def test_role_granting(self):
        """Test role granting."""
        user_id = "test_user"
        role_name = "viewer"
        
        self.auth_bridge.grant_role_to_user(user_id, role_name)
        
        # Check role permissions
        has_permission = self.auth_bridge.check_permission(user_id, "rate_limit.read")
        self.assertTrue(has_permission)
        
        # Check non-role permission
        has_permission = self.auth_bridge.check_permission(user_id, "rate_limit.admin")
        self.assertFalse(has_permission)


class PerformanceMonitorTest(TestCase):
    """Test performance monitor."""
    
    def setUp(self):
        self.performance_monitor = PerformanceMonitor()
    
    def test_metric_recording(self):
        """Test metric recording."""
        self.performance_monitor.record_metric("test_metric", 42.5)
        
        values = self.performance_monitor.get_metric_values("test_metric")
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0].value, 42.5)
    
    def test_counter_increment(self):
        """Test counter increment."""
        self.performance_monitor.increment_counter("test_counter")
        self.performance_monitor.increment_counter("test_counter")
        
        values = self.performance_monitor.get_metric_values("test_counter")
        self.assertEqual(len(values), 2)
        self.assertEqual(values[0].value, 2.0)  # Latest value
        self.assertEqual(values[1].value, 1.0)  # Previous value
    
    def test_statistics(self):
        """Test statistics calculation."""
        # Record some metrics
        self.performance_monitor.record_metric("test_metric", 10.0)
        self.performance_monitor.record_metric("test_metric", 20.0)
        self.performance_monitor.record_metric("test_metric", 30.0)
        
        stats = self.performance_monitor.get_metric_statistics("test_metric")
        
        self.assertEqual(stats["count"], 3)
        self.assertEqual(stats["min"], 10.0)
        self.assertEqual(stats["max"], 30.0)
        self.assertEqual(stats["avg"], 20.0)


class HealthCheckerTest(TestCase):
    """Test health checker."""
    
    def setUp(self):
        self.health_checker = HealthChecker()
    
    def test_health_check_registration(self):
        """Test health check registration."""
        from .health_check import HealthCheck, CheckType
        
        check = HealthCheck(
            name="test_check",
            check_type=CheckType.CUSTOM,
            description="Test health check"
        )
        
        self.health_checker.register_health_check(check)
        
        self.assertIn("test_check", self.health_checker.health_checks)
    
    def test_system_health(self):
        """Test system health calculation."""
        health = self.health_checker.get_system_health()
        
        self.assertIsNotNone(health)
        self.assertIn(health.status, [status.value for status in HealthStatus])
        self.assertGreaterEqual(health.score, 0.0)
        self.assertLessEqual(health.score, 100.0)


class SyncManagerTest(TestCase):
    """Test sync manager."""
    
    def setUp(self):
        self.sync_manager = SyncManager()
    
    def test_conflict_detection(self):
        """Test conflict detection."""
        source_data = {"name": "John", "age": 30}
        target_data = {"name": "Jane", "age": 30}
        
        conflicts = self.sync_manager.detect_conflicts("test_bridge", source_data, target_data)
        
        # Should detect conflict for 'name' field
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].field_name, "name")
        self.assertEqual(conflicts[0].source_value, "John")
        self.assertEqual(conflicts[0].target_value, "Jane")
    
    def test_conflict_resolution(self):
        """Test conflict resolution."""
        from .sync_manager import Conflict, ConflictType, ConflictSeverity
        
        conflict = Conflict(
            conflict_id="test_conflict",
            bridge_name="test_bridge",
            conflict_type=ConflictType.DATA_CONFLICT,
            severity=ConflictSeverity.MEDIUM,
            source_data={"name": "John"},
            target_data={"name": "Jane"},
            field_name="name",
            source_value="John",
            target_value="Jane"
        )
        
        # Create sync conflict
        sync_id = self.sync_manager.create_sync_conflict("test_bridge", [conflict])
        
        self.assertIsNotNone(sync_id)
        sync_conflict = self.sync_manager.get_conflict(sync_id)
        self.assertEqual(len(sync_conflict.conflicts), 1)


class IntegrationSystemTest(TransactionTestCase):
    """Integration tests for the entire system."""
    
    def setUp(self):
        # Clear cache
        cache.clear()
    
    def test_end_to_end_integration(self):
        """Test end-to-end integration flow."""
        # 1. Create event
        event = Event("rate_limit_exceeded", {
            "user_id": "test_user",
            "ip_address": "127.0.0.1",
            "endpoint": "/api/test"
        })
        
        # 2. Publish event
        event_bus = EventBus()
        asyncio.run(event_bus.publish(event))
        
        # 3. Verify event was processed
        self.assertIn("rate_limit_exceeded", event_bus.event_history)
        
        # 4. Check performance metrics
        performance_monitor = PerformanceMonitor()
        performance_monitor.record_metric("events_processed", 1)
        
        stats = performance_monitor.get_statistics()
        self.assertGreater(stats['total_metrics'], 0)
    
    def test_fault_tolerance(self):
        """Test fault tolerance mechanisms."""
        # Test circuit breaker
        circuit_breaker = CircuitBreaker("test", failure_threshold=2)
        
        # Simulate failures
        for i in range(3):
            try:
                circuit_breaker.call(lambda: 1/0)  # This will fail
            except:
                pass
        
        # Circuit should be open
        self.assertEqual(circuit_breaker.get_state().value, "open")
        
        # Test fallback
        fallback_manager = FallbackManager()
        
        config = fallback_manager.create_immediate_fallback(
            "test_fallback",
            default_value="fallback_result"
        )
        
        fallback_manager.register_fallback_config(config)
        
        result = fallback_manager.execute_fallback(
            "test_fallback",
            Exception("Test error")
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.result, "fallback_result")
    
    def test_security_validation(self):
        """Test security and validation."""
        # Test data validation
        validator = DataValidator()
        
        schema = {
            "user_id": {"type": ValidationType.REQUIRED},
            "email": {"type": ValidationType.FORMAT, "pattern": r"[^@]+@[^@]+\.[^@]+"}
        }
        
        # Valid data
        valid_data = {"user_id": "test", "email": "test@example.com"}
        result = validator.validate(valid_data, schema)
        self.assertTrue(result.is_valid)
        
        # Invalid data
        invalid_data = {"user_id": "test", "email": "invalid_email"}
        result = validator.validate(invalid_data, schema)
        self.assertFalse(result.is_valid)
        
        # Test authentication
        auth_bridge = AuthBridge()
        auth_bridge.grant_permission_to_user("test_user", "rate_limit.read")
        
        has_permission = auth_bridge.check_permission("test_user", "rate_limit.read")
        self.assertTrue(has_permission)
        
        # Test audit logging
        audit_logger = AuditLogger()
        audit_logger.log_security_event(
            action="login",
            resource_type="user",
            user_id="test_user"
        )
        
        stats = audit_logger.get_statistics()
        self.assertGreater(stats['total_logs'], 0)


class PerformanceTest(TransactionTestCase):
    """Performance tests for the integration system."""
    
    def test_event_bus_performance(self):
        """Test event bus performance."""
        event_bus = EventBus()
        
        # Subscribe multiple handlers
        def test_handler(event):
            pass
        
        for i in range(100):
            event_bus.subscribe(f"test_event_{i}", test_handler)
        
        # Publish events and measure time
        start_time = time.time()
        
        for i in range(1000):
            event = Event(f"test_event_{i % 100}", {"data": f"test_{i}"})
            asyncio.run(event_bus.publish(event))
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete within reasonable time (adjust threshold as needed)
        self.assertLess(duration, 5.0)  # 5 seconds for 1000 events
    
    def test_message_queue_performance(self):
        """Test message queue performance."""
        queue_manager = MessageQueueManager()
        queue_manager.create_queue("perf_test", QueueType.FIFO)
        
        # Enqueue performance
        start_time = time.time()
        
        for i in range(1000):
            queue_manager.enqueue("perf_test", {"id": i, "data": f"test_{i}"})
        
        enqueue_time = time.time() - start_time
        
        # Dequeue performance
        start_time = time.time()
        
        for i in range(1000):
            queue_manager.dequeue("perf_test")
        
        dequeue_time = time.time() - start_time
        
        # Should complete within reasonable time
        self.assertLess(enqueue_time, 2.0)  # 2 seconds for 1000 enqueues
        self.assertLess(dequeue_time, 2.0)  # 2 seconds for 1000 dequeues


if __name__ == '__main__':
    unittest.main()
