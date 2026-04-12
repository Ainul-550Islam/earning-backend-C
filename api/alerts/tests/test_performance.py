"""
Performance Tests for Alerts API
"""
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.db import connection
from django.test.utils import override_settings
from datetime import timedelta
import time
import json

from alerts.models.core import AlertRule, AlertLog, Notification, SystemMetrics
from alerts.models.threshold import ThresholdConfig, ThresholdBreach
from alerts.models.channel import AlertChannel, ChannelRoute
from alerts.models.incident import Incident
from alerts.services.core import AlertProcessingService
from alerts.tasks.core import ProcessAlertsTask


class AlertProcessingPerformanceTest(TransactionTestCase):
    """Performance tests for alert processing"""
    
    def setUp(self):
        # Create test data
        self.alert_rule = AlertRule.objects.create(
            name='Performance Test Alert',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0,
            is_active=True
        )
        
        self.service = AlertProcessingService()
    
    def test_process_single_alert_performance(self):
        """Test processing single alert performance"""
        # Create alert
        alert = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Performance test alert'
        )
        
        # Measure processing time
        start_time = time.time()
        
        result = self.service.process_single_alert(alert.id)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Performance assertion
        self.assertLess(processing_time, 1.0)  # Should complete within 1 second
        self.assertTrue(result['success'])
    
    def test_process_batch_alerts_performance(self):
        """Test processing batch alerts performance"""
        # Create multiple alerts
        alerts = []
        for i in range(100):
            alert = AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Batch alert {i}'
            )
            alerts.append(alert)
        
        # Measure batch processing time
        start_time = time.time()
        
        processed_count = 0
        for alert in alerts:
            result = self.service.process_single_alert(alert.id)
            if result['success']:
                processed_count += 1
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Performance assertions
        self.assertLess(processing_time, 10.0)  # Should complete within 10 seconds
        self.assertEqual(processed_count, 100)
        self.assertLess(processing_time / 100, 0.1)  # Average < 100ms per alert
    
    def test_alert_creation_performance(self):
        """Test alert creation performance"""
        # Measure alert creation time
        start_time = time.time()
        
        alerts = []
        for i in range(1000):
            alert = AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Performance alert {i}',
                details={'iteration': i, 'timestamp': timezone.now().isoformat()}
            )
            alerts.append(alert)
        
        end_time = time.time()
        creation_time = end_time - start_time
        
        # Performance assertions
        self.assertLess(creation_time, 5.0)  # Should complete within 5 seconds
        self.assertEqual(len(alerts), 1000)
        self.assertLess(creation_time / 1000, 0.005)  # Average < 5ms per alert
    
    def test_notification_creation_performance(self):
        """Test notification creation performance"""
        # Create alert first
        alert = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Notification test alert'
        )
        
        # Measure notification creation time
        start_time = time.time()
        
        notifications = []
        for i in range(500):
            notification = Notification.objects.create(
                alert_log=alert,
                notification_type='email',
                recipient=f'test{i}@example.com',
                status='pending'
            )
            notifications.append(notification)
        
        end_time = time.time()
        creation_time = end_time - start_time
        
        # Performance assertions
        self.assertLess(creation_time, 3.0)  # Should complete within 3 seconds
        self.assertEqual(len(notifications), 500)
        self.assertLess(creation_time / 500, 0.006)  # Average < 6ms per notification
    
    def test_alert_query_performance(self):
        """Test alert query performance"""
        # Create test data
        for i in range(1000):
            AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Query test alert {i}',
                is_resolved=i % 3 == 0,
                triggered_at=timezone.now() - timedelta(hours=i)
            )
        
        # Measure query time
        start_time = time.time()
        
        # Test different query patterns
        queries = [
            AlertLog.objects.all(),
            AlertLog.objects.filter(is_resolved=True),
            AlertLog.objects.filter(triggered_at__gte=timezone.now() - timedelta(hours=24)),
            AlertLog.objects.filter(rule=self.alert_rule),
            AlertLog.objects.filter(is_resolved=False).order_by('-triggered_at')[:100]
        ]
        
        for query in queries:
            list(query)  # Execute query
        
        end_time = time.time()
        query_time = end_time - start_time
        
        # Performance assertions
        self.assertLess(query_time, 2.0)  # Should complete within 2 seconds
    
    def test_complex_filtering_performance(self):
        """Test complex filtering performance"""
        # Create test data
        for i in range(500):
            AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Filter test alert {i}',
                is_resolved=i % 3 == 0,
                triggered_at=timezone.now() - timedelta(hours=i)
            )
        
        # Measure complex query time
        start_time = time.time()
        
        # Complex filtering
        alerts = AlertLog.objects.filter(
            rule=self.alert_rule,
            is_resolved=False,
            triggered_at__gte=timezone.now() - timedelta(hours=24),
            trigger_value__gte=85.0
        ).order_by('-triggered_at')[:50]
        
        list(alerts)  # Execute query
        
        end_time = time.time()
        query_time = end_time - start_time
        
        # Performance assertions
        self.assertLess(query_time, 1.0)  # Should complete within 1 second


class DatabasePerformanceTest(TransactionTestCase):
    """Database performance tests"""
    
    def setUp(self):
        # Create test data
        self.alert_rules = []
        for i in range(10):
            rule = AlertRule.objects.create(
                name=f'Perf Test Rule {i}',
                alert_type='cpu_usage',
                severity='high' if i % 2 == 0 else 'medium',
                threshold_value=80.0
            )
            self.alert_rules.append(rule)
    
    def test_bulk_insert_performance(self):
        """Test bulk insert performance"""
        # Prepare bulk data
        alerts_data = []
        for i in range(1000):
            rule = self.alert_rules[i % len(self.alert_rules)]
            alerts_data.append(AlertLog(
                rule=rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Bulk alert {i}',
                details={'bulk': True, 'index': i}
            ))
        
        # Measure bulk insert time
        start_time = time.time()
        
        AlertLog.objects.bulk_create(alerts_data, batch_size=100)
        
        end_time = time.time()
        insert_time = end_time - start_time
        
        # Performance assertions
        self.assertLess(insert_time, 3.0)  # Should complete within 3 seconds
        self.assertEqual(AlertLog.objects.count(), 1000)
        self.assertLess(insert_time / 1000, 0.003)  # Average < 3ms per record
    
    def test_bulk_update_performance(self):
        """Test bulk update performance"""
        # Create test data first
        alerts = []
        for i in range(500):
            alert = AlertLog.objects.create(
                rule=self.alert_rules[i % len(self.alert_rules)],
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Update test alert {i}'
            )
            alerts.append(alert)
        
        # Measure bulk update time
        start_time = time.time()
        
        # Bulk update
        AlertLog.objects.filter(id__in=[alert.id for alert in alerts]).update(
            is_resolved=True,
            resolution_note='Bulk resolved',
            resolved_at=timezone.now()
        )
        
        end_time = time.time()
        update_time = end_time - start_time
        
        # Performance assertions
        self.assertLess(update_time, 2.0)  # Should complete within 2 seconds
        self.assertLess(update_time / 500, 0.004)  # Average < 4ms per update
    
    def test_index_usage_performance(self):
        """Test index usage performance"""
        # Create test data
        for i in range(1000):
            AlertLog.objects.create(
                rule=self.alert_rules[i % len(self.alert_rules)],
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Index test alert {i}',
                is_resolved=i % 3 == 0,
                triggered_at=timezone.now() - timedelta(hours=i)
            )
        
        # Measure indexed query time
        start_time = time.time()
        
        # Query using indexes
        alerts = AlertLog.objects.filter(
            rule=self.alert_rules[0],
            is_resolved=False,
            triggered_at__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-triggered_at')[:100]
        
        list(alerts)  # Execute query
        
        end_time = time.time()
        query_time = end_time - start_time
        
        # Performance assertions
        self.assertLess(query_time, 0.5)  # Should complete within 0.5 seconds
        
        # Check query plan (simplified check)
        with connection.cursor() as cursor:
            cursor.execute("EXPLAIN ANALYZE SELECT * FROM alerts_alertlog WHERE rule_id = %s AND is_resolved = %s AND triggered_at >= %s ORDER BY triggered_at DESC LIMIT 100", 
                         [self.alert_rules[0].id, False, (timezone.now() - timedelta(hours=24))])
            explain_result = cursor.fetchall()
            
            # Should use index (simplified check)
            explain_text = str(explain_result)
            self.assertIn('Index', explain_text) or self.assertIn('Bitmap', explain_text)
    
    def test_connection_pooling_performance(self):
        """Test database connection pooling performance"""
        # Simulate concurrent operations
        start_time = time.time()
        
        # Multiple rapid queries
        for i in range(100):
            AlertLog.objects.filter(
                rule=self.alert_rules[i % len(self.alert_rules)]
            ).count()
        
        end_time = time.time()
        query_time = end_time - start_time
        
        # Performance assertions
        self.assertLess(query_time, 2.0)  # Should complete within 2 seconds
        self.assertLess(query_time / 100, 0.02)  # Average < 20ms per query


class MemoryUsageTest(TransactionTestCase):
    """Memory usage tests"""
    
    def setUp(self):
        self.alert_rule = AlertRule.objects.create(
            name='Memory Test Alert',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
    
    def test_large_dataset_memory_usage(self):
        """Test memory usage with large datasets"""
        import gc
        import sys
        
        # Get initial memory usage
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Create large dataset
        alerts = []
        for i in range(5000):
            alert = AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Memory test alert {i}',
                details={
                    'large_data': 'x' * 1000,  # 1KB per record
                    'metadata': {'index': i, 'batch': i // 100}
                }
            )
            alerts.append(alert)
            
            # Check memory usage periodically
            if i % 1000 == 0:
                gc.collect()
                current_objects = len(gc.get_objects())
                object_increase = current_objects - initial_objects
                
                # Memory usage should be reasonable
                self.assertLess(object_increase, 50000)  # Less than 50k objects increase
        
        # Final memory check
        gc.collect()
        final_objects = len(gc.get_objects())
        total_increase = final_objects - initial_objects
        
        # Memory usage should be reasonable for 5000 records
        self.assertLess(total_increase, 100000)  # Less than 100k objects increase
    
    def test_query_memory_efficiency(self):
        """Test query memory efficiency"""
        # Create test data
        for i in range(1000):
            AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Memory query test {i}'
            )
        
        # Test iterator-based query (memory efficient)
        start_time = time.time()
        
        processed_count = 0
        for alert in AlertLog.objects.iterator():
            # Process alert
            processed_count += 1
            if processed_count >= 1000:
                break
        
        end_time = time.time()
        query_time = end_time - start_time
        
        # Performance assertions
        self.assertLess(query_time, 2.0)  # Should complete within 2 seconds
        self.assertEqual(processed_count, 1000)
    
    def test_bulk_operations_memory_efficiency(self):
        """Test bulk operations memory efficiency"""
        # Test bulk create memory efficiency
        alerts_data = []
        for i in range(2000):
            alerts_data.append(AlertLog(
                rule=self.alert_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Bulk memory test {i}'
            ))
        
        # Measure memory usage during bulk create
        start_time = time.time()
        
        AlertLog.objects.bulk_create(alerts_data, batch_size=200)
        
        end_time = time.time()
        create_time = end_time - start_time
        
        # Performance assertions
        self.assertLess(create_time, 5.0)  # Should complete within 5 seconds
        self.assertEqual(AlertLog.objects.count(), 2000)


class ConcurrentOperationsTest(TransactionTestCase):
    """Concurrent operations tests"""
    
    def setUp(self):
        self.alert_rule = AlertRule.objects.create(
            name='Concurrent Test Alert',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
    
    def test_concurrent_alert_creation(self):
        """Test concurrent alert creation"""
        import threading
        import queue
        
        results = queue.Queue()
        
        def create_alerts(alert_range, thread_id):
            """Create alerts in a separate thread"""
            try:
                alerts_created = []
                for i in alert_range:
                    alert = AlertLog.objects.create(
                        rule=self.alert_rule,
                        trigger_value=85.0 + i,
                        threshold_value=80.0,
                        message=f'Concurrent alert {thread_id}-{i}'
                    )
                    alerts_created.append(alert.id)
                
                results.put(('success', thread_id, len(alerts_created)))
            except Exception as e:
                results.put(('error', thread_id, str(e)))
        
        # Create multiple threads
        threads = []
        start_time = time.time()
        
        for i in range(5):
            thread = threading.Thread(
                target=create_alerts,
                args=(range(i * 100, (i + 1) * 100), i)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Collect results
        success_count = 0
        error_count = 0
        total_created = 0
        
        while not results.empty():
            status, thread_id, count = results.get()
            if status == 'success':
                success_count += 1
                total_created += count
            else:
                error_count += 1
        
        # Performance assertions
        self.assertLess(total_time, 10.0)  # Should complete within 10 seconds
        self.assertEqual(success_count, 5)  # All threads should succeed
        self.assertEqual(error_count, 0)  # No errors
        self.assertEqual(total_created, 500)  # All alerts created
    
    def test_concurrent_alert_processing(self):
        """Test concurrent alert processing"""
        import threading
        import queue
        
        # Create alerts first
        alerts = []
        for i in range(100):
            alert = AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Concurrent processing test {i}'
            )
            alerts.append(alert)
        
        results = queue.Queue()
        
        def process_alerts(alert_ids, thread_id):
            """Process alerts in a separate thread"""
            try:
                service = AlertProcessingService()
                processed_count = 0
                
                for alert_id in alert_ids:
                    result = service.process_single_alert(alert_id)
                    if result['success']:
                        processed_count += 1
                
                results.put(('success', thread_id, processed_count))
            except Exception as e:
                results.put(('error', thread_id, str(e)))
        
        # Create multiple threads for processing
        threads = []
        start_time = time.time()
        
        # Split alerts among threads
        alerts_per_thread = len(alerts) // 5
        for i in range(5):
            start_idx = i * alerts_per_thread
            end_idx = start_idx + alerts_per_thread if i < 4 else len(alerts)
            thread_alerts = alerts[start_idx:end_idx]
            thread_ids = [alert.id for alert in thread_alerts]
            
            thread = threading.Thread(
                target=process_alerts,
                args=(thread_ids, i)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Collect results
        success_count = 0
        error_count = 0
        total_processed = 0
        
        while not results.empty():
            status, thread_id, count = results.get()
            if status == 'success':
                success_count += 1
                total_processed += count
            else:
                error_count += 1
        
        # Performance assertions
        self.assertLess(total_time, 15.0)  # Should complete within 15 seconds
        self.assertEqual(success_count, 5)  # All threads should succeed
        self.assertEqual(error_count, 0)  # No errors
        self.assertEqual(total_processed, 100)  # All alerts processed
    
    def test_concurrent_notifications(self):
        """Test concurrent notification creation"""
        import threading
        import queue
        
        # Create alerts first
        alerts = []
        for i in range(200):
            alert = AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Concurrent notification test {i}'
            )
            alerts.append(alert)
        
        results = queue.Queue()
        
        def create_notifications(alert_ids, thread_id):
            """Create notifications in a separate thread"""
            try:
                notifications_created = []
                for alert_id in alert_ids:
                    notification = Notification.objects.create(
                        alert_log_id=alert_id,
                        notification_type='email',
                        recipient=f'test{thread_id}-{alert_id}@example.com',
                        status='pending'
                    )
                    notifications_created.append(notification.id)
                
                results.put(('success', thread_id, len(notifications_created)))
            except Exception as e:
                results.put(('error', thread_id, str(e)))
        
        # Create multiple threads
        threads = []
        start_time = time.time()
        
        # Split alerts among threads
        alerts_per_thread = len(alerts) // 4
        for i in range(4):
            start_idx = i * alerts_per_thread
            end_idx = start_idx + alerts_per_thread if i < 3 else len(alerts)
            thread_alerts = alerts[start_idx:end_idx]
            thread_ids = [alert.id for alert in thread_alerts]
            
            thread = threading.Thread(
                target=create_notifications,
                args=(thread_ids, i)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Collect results
        success_count = 0
        error_count = 0
        total_created = 0
        
        while not results.empty():
            status, thread_id, count = results.get()
            if status == 'success':
                success_count += 1
                total_created += count
            else:
                error_count += 1
        
        # Performance assertions
        self.assertLess(total_time, 8.0)  # Should complete within 8 seconds
        self.assertEqual(success_count, 4)  # All threads should succeed
        self.assertEqual(error_count, 0)  # No errors
        self.assertEqual(total_created, 200)  # All notifications created


class ScalabilityTest(TransactionTestCase):
    """Scalability tests"""
    
    def setUp(self):
        # Create multiple alert rules
        self.alert_rules = []
        for i in range(20):
            rule = AlertRule.objects.create(
                name=f'Scalability Test Rule {i}',
                alert_type='cpu_usage',
                severity='high' if i % 2 == 0 else 'medium',
                threshold_value=80.0
            )
            self.alert_rules.append(rule)
    
    def test_large_scale_alert_creation(self):
        """Test large-scale alert creation"""
        # Create 10,000 alerts
        start_time = time.time()
        
        alerts_data = []
        for i in range(10000):
            rule = self.alert_rules[i % len(self.alert_rules)]
            alerts_data.append(AlertLog(
                rule=rule,
                trigger_value=85.0 + (i % 20),
                threshold_value=80.0,
                message=f'Scale test alert {i}',
                details={'scale_test': True, 'index': i}
            ))
        
        # Bulk create in batches
        batch_size = 1000
        for i in range(0, len(alerts_data), batch_size):
            batch = alerts_data[i:i + batch_size]
            AlertLog.objects.bulk_create(batch, batch_size=batch_size)
        
        end_time = time.time()
        creation_time = end_time - start_time
        
        # Performance assertions
        self.assertLess(creation_time, 30.0)  # Should complete within 30 seconds
        self.assertEqual(AlertLog.objects.count(), 10000)
        self.assertLess(creation_time / 10000, 0.003)  # Average < 3ms per alert
    
    def test_large_scale_query_performance(self):
        """Test large-scale query performance"""
        # Create large dataset
        for i in range(5000):
            AlertLog.objects.create(
                rule=self.alert_rules[i % len(self.alert_rules)],
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Query scale test {i}',
                is_resolved=i % 3 == 0,
                triggered_at=timezone.now() - timedelta(hours=i)
            )
        
        # Test various query patterns
        queries_to_test = [
            # Simple filter
            lambda: AlertLog.objects.filter(rule=self.alert_rules[0]).count(),
            
            # Complex filter
            lambda: AlertLog.objects.filter(
                rule__in=self.alert_rules[:5],
                is_resolved=False,
                triggered_at__gte=timezone.now() - timedelta(hours=24)
            ).count(),
            
            # Ordered query
            lambda: list(AlertLog.objects.filter(
                rule=self.alert_rules[0]
            ).order_by('-triggered_at')[:100]),
            
            # Aggregation
            lambda: AlertLog.objects.filter(
                rule__in=self.alert_rules[:10]
            ).values('rule').annotate(count=models.Count('id')),
            
            # Date range query
            lambda: AlertLog.objects.filter(
                triggered_at__range=[
                    timezone.now() - timedelta(days=7),
                    timezone.now()
                ]
            ).count()
        ]
        
        # Test each query
        for i, query_func in enumerate(queries_to_test):
            start_time = time.time()
            
            result = query_func()
            
            end_time = time.time()
            query_time = end_time - start_time
            
            # Performance assertions
            self.assertLess(query_time, 2.0, f"Query {i} took too long: {query_time}s")
    
    def test_memory_usage_at_scale(self):
        """Test memory usage at scale"""
        import gc
        
        # Get baseline memory
        gc.collect()
        baseline_objects = len(gc.get_objects())
        
        # Create large dataset
        for i in range(3000):
            AlertLog.objects.create(
                rule=self.alert_rules[i % len(self.alert_rules)],
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Memory scale test {i}',
                details={
                    'data': 'x' * 500,  # 500 bytes per record
                    'metadata': {'index': i, 'timestamp': timezone.now().isoformat()}
                }
            )
        
        # Check memory usage
        gc.collect()
        current_objects = len(gc.get_objects())
        object_increase = current_objects - baseline_objects
        
        # Memory usage should be reasonable
        self.assertLess(object_increase, 150000)  # Less than 150k objects increase
    
    def test_concurrent_operations_at_scale(self):
        """Test concurrent operations at scale"""
        import threading
        import queue
        
        # Create alerts for concurrent processing
        alerts = []
        for i in range(1000):
            alert = AlertLog.objects.create(
                rule=self.alert_rules[i % len(self.alert_rules)],
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Concurrent scale test {i}'
            )
            alerts.append(alert)
        
        results = queue.Queue()
        
        def process_batch(alert_batch, thread_id):
            """Process batch of alerts"""
            try:
                service = AlertProcessingService()
                processed = 0
                
                for alert in alert_batch:
                    result = service.process_single_alert(alert.id)
                    if result['success']:
                        processed += 1
                
                results.put(('success', thread_id, processed))
            except Exception as e:
                results.put(('error', thread_id, str(e)))
        
        # Create threads for concurrent processing
        threads = []
        start_time = time.time()
        
        # Split alerts among threads
        batch_size = len(alerts) // 10
        for i in range(10):
            start_idx = i * batch_size
            end_idx = start_idx + batch_size if i < 9 else len(alerts)
            batch = alerts[start_idx:end_idx]
            
            thread = threading.Thread(
                target=process_batch,
                args=(batch, i)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Collect results
        success_count = 0
        error_count = 0
        total_processed = 0
        
        while not results.empty():
            status, thread_id, count = results.get()
            if status == 'success':
                success_count += 1
                total_processed += count
            else:
                error_count += 1
        
        # Performance assertions
        self.assertLess(total_time, 20.0)  # Should complete within 20 seconds
        self.assertEqual(success_count, 10)  # All threads should succeed
        self.assertEqual(error_count, 0)  # No errors
        self.assertEqual(total_processed, 1000)  # All alerts processed
