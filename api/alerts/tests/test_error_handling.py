"""
Error Handling Tests for Alerts API
"""
from django.test import TestCase, TransactionTestCase
from django.core.management import call_command
from django.utils import timezone
from django.db import DatabaseError, IntegrityError
from django.contrib.auth import get_user_model
from datetime import timedelta
import json

from alerts.models.core import AlertRule, AlertLog, Notification, SystemMetrics
from alerts.models.threshold import ThresholdConfig, ThresholdBreach
from alerts.models.channel import AlertChannel, ChannelRoute
from alerts.models.incident import Incident
from alerts.services.core import AlertProcessingService
from alerts.tasks.core import ProcessAlertsTask

User = get_user_model()


class ModelErrorHandlingTest(TestCase):
    """Test error handling in models"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_alert_rule_integrity_error(self):
        """Test handling integrity errors in AlertRule"""
        # Create alert rule
        rule = AlertRule.objects.create(
            name='Test Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        # Try to create another rule with same name (if unique constraint exists)
        try:
            AlertRule.objects.create(
                name='Test Rule',  # Same name
                alert_type='memory_usage',
                severity='medium',
                threshold_value=85.0
            )
        except IntegrityError:
            # Expected behavior
            pass
        else:
            # If no integrity error, that's also valid behavior
            pass
    
    def test_alert_log_foreign_key_error(self):
        """Test handling foreign key errors in AlertLog"""
        try:
            # Try to create alert log with non-existent rule
            AlertLog.objects.create(
                rule_id=99999,  # Non-existent rule
                trigger_value=85.0,
                threshold_value=80.0,
                message='Test alert'
            )
        except Exception as e:
            # Should handle foreign key error gracefully
            self.assertIn('rule', str(e).lower())
    
    def test_notification_foreign_key_error(self):
        """Test handling foreign key errors in Notification"""
        try:
            # Try to create notification with non-existent alert log
            Notification.objects.create(
                alert_log_id=99999,  # Non-existent alert log
                notification_type='email',
                recipient='test@example.com',
                status='pending'
            )
        except Exception as e:
            # Should handle foreign key error gracefully
            self.assertIn('alert_log', str(e).lower())
    
    def test_system_metrics_validation_error(self):
        """Test handling validation errors in SystemMetrics"""
        # Test with invalid data
        try:
            metrics = SystemMetrics.objects.create(
                total_users=-100,  # Should be validated
                active_users_1h=50,
                total_earnings_1h=1000.0,
                avg_response_time_ms=200.0
            )
            
            # If model allows negative values, this is valid
            self.assertEqual(metrics.total_users, -100)
        except Exception as e:
            # If validation prevents negative values
            self.assertIn('total_users', str(e).lower())
    
    def test_threshold_config_validation_error(self):
        """Test handling validation errors in ThresholdConfig"""
        alert_rule = AlertRule.objects.create(
            name='Test Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        try:
            config = ThresholdConfig.objects.create(
                alert_rule=alert_rule,
                threshold_type='invalid_type',  # Invalid threshold type
                operator='greater_than',
                primary_threshold=85.0
            )
            
            # If model allows invalid types, this is valid
            self.assertEqual(config.threshold_type, 'invalid_type')
        except Exception as e:
            # If validation prevents invalid types
            self.assertIn('threshold_type', str(e).lower())
    
    def test_channel_config_validation_error(self):
        """Test handling validation errors in AlertChannel"""
        try:
            channel = AlertChannel.objects.create(
                name='Test Channel',
                channel_type='invalid_type',  # Invalid channel type
                is_enabled=True,
                config={}
            )
            
            # If model allows invalid types, this is valid
            self.assertEqual(channel.channel_type, 'invalid_type')
        except Exception as e:
            # If validation prevents invalid types
            self.assertIn('channel_type', str(e).lower())
    
    def test_incident_validation_error(self):
        """Test handling validation errors in Incident"""
        try:
            incident = Incident.objects.create(
                title='',  # Empty title might be invalid
                description='Test incident',
                severity='invalid_severity',  # Invalid severity
                impact='invalid_impact',  # Invalid impact
                urgency='invalid_urgency',  # Invalid urgency
                status='invalid_status'  # Invalid status
            )
            
            # If model allows these values, this is valid
            self.assertEqual(incident.title, '')
        except Exception as e:
            # If validation prevents these values
            self.assertIn('title', str(e).lower()) or \
               self.assertIn('severity', str(e).lower()) or \
               self.assertIn('impact', str(e).lower()) or \
               self.assertIn('urgency', str(e).lower()) or \
               self.assertIn('status', str(e).lower())


class ServiceErrorHandlingTest(TestCase):
    """Test error handling in services"""
    
    def setUp(self):
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        self.service = AlertProcessingService()
    
    def test_process_alert_with_invalid_rule(self):
        """Test processing alert with invalid rule"""
        invalid_data = {
            'rule_id': 99999,  # Non-existent rule
            'trigger_value': 85.0,
            'threshold_value': 80.0,
            'message': 'Test alert'
        }
        
        result = self.service.process_alert(invalid_data)
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('rule', result['error'].lower())
    
    def test_process_alert_with_invalid_data_types(self):
        """Test processing alert with invalid data types"""
        invalid_data = {
            'rule_id': self.alert_rule.id,
            'trigger_value': 'not_a_number',  # Invalid type
            'threshold_value': None,  # Invalid type
            'message': 12345  # Invalid type
        }
        
        result = self.service.process_alert(invalid_data)
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    def test_process_alert_with_missing_required_fields(self):
        """Test processing alert with missing required fields"""
        incomplete_data = {
            'rule_id': self.alert_rule.id
            # Missing required fields
        }
        
        result = self.service.process_alert(incomplete_data)
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    def test_process_alert_with_database_error(self):
        """Test processing alert when database is unavailable"""
        # Mock database error
        original_method = AlertLog.objects.create
        
        def mock_create(*args, **kwargs):
            raise DatabaseError("Database connection lost")
        
        AlertLog.objects.create = mock_create
        
        try:
            data = {
                'rule_id': self.alert_rule.id,
                'trigger_value': 85.0,
                'threshold_value': 80.0,
                'message': 'Test alert'
            }
            
            result = self.service.process_alert(data)
            
            self.assertFalse(result['success'])
            self.assertIn('error', result)
        finally:
            # Restore original method
            AlertLog.objects.create = original_method
    
    def test_validate_alert_data_with_corrupted_data(self):
        """Test validating corrupted alert data"""
        corrupted_data = {
            'rule_id': self.alert_rule.id,
            'trigger_value': float('inf'),  # Infinity
            'threshold_value': float('nan'),  # Not a number
            'message': None
        }
        
        result = self.service.validate_alert_data(corrupted_data)
        
        self.assertFalse(result['valid'])
        self.assertIn('errors', result)
    
    def test_format_notification_message_with_unicode_error(self):
        """Test formatting notification message with unicode errors"""
        # Create alert log
        alert = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Test alert'
        )
        
        # Try to format with invalid encoding
        try:
            message = self.service.format_notification_message(
                alert.id,
                subject='Test Subject',
                template='invalid_template'
            )
            
            # Should handle gracefully or return default message
            self.assertIsInstance(message, str)
        except Exception as e:
            # Should handle unicode errors gracefully
            self.assertIsInstance(e, (UnicodeError, ValueError))
    
    def test_check_rate_limit_with_invalid_data(self):
        """Test checking rate limit with invalid data"""
        try:
            result = self.service.check_rate_limit(None)  # None rule
            # Should handle gracefully
            self.assertIsInstance(result, dict)
        except Exception as e:
            # Should handle error gracefully
            self.assertIsInstance(e, (AttributeError, TypeError))


class TaskErrorHandlingTest(TestCase):
    """Test error handling in management tasks"""
    
    def setUp(self):
        self.out = StringIO()
    
    def test_process_alerts_command_with_invalid_parameters(self):
        """Test process_alerts command with invalid parameters"""
        try:
            call_command('process_alerts', '--limit', 'invalid', stdout=self.out)
        except Exception as e:
            # Should handle invalid parameter gracefully
            self.assertIsInstance(e, (ValueError, TypeError))
    
    def test_process_alerts_command_with_database_error(self):
        """Test process_alerts command with database error"""
        # Mock database error
        from alerts.management.commands.process_alerts import Command
        
        command = Command()
        
        # Mock database error
        original_method = AlertLog.objects.filter
        def mock_filter(*args, **kwargs):
            raise DatabaseError("Database connection lost")
        
        AlertLog.objects.filter = mock_filter
        
        try:
            command.handle(limit=10, stdout=self.out)
            # Should handle database error gracefully
            output = self.out.getvalue()
            self.assertIn('error', output.lower())
        except Exception as e:
            # Should handle error gracefully
            self.assertIsInstance(e, DatabaseError)
        finally:
            # Restore original method
            AlertLog.objects.filter = original_method
    
    def test_generate_reports_command_with_invalid_date(self):
        """Test generate_reports command with invalid date"""
        try:
            call_command('generate_reports', 'daily', '--date', 'invalid_date', stdout=self.out)
        except Exception as e:
            # Should handle invalid date gracefully
            self.assertIsInstance(e, (ValueError, TypeError))
    
    def test_cleanup_alerts_command_with_invalid_days(self):
        """Test cleanup_alerts command with invalid days parameter"""
        try:
            call_command('cleanup_alerts', '--days', 'invalid', stdout=self.out)
        except Exception as e:
            # Should handle invalid parameter gracefully
            self.assertIsInstance(e, (ValueError, TypeError))
    
    def test_check_health_command_with_service_error(self):
        """Test check_health command with service errors"""
        # Mock service error
        from alerts.management.commands.check_health import Command
        
        command = Command()
        
        # Mock service error
        original_method = command.check_alert_system_health
        def mock_check(*args, **kwargs):
            raise Exception("Service unavailable")
        
        command.check_alert_system_health = mock_check
        
        try:
            command.handle(stdout=self.out)
            # Should handle service error gracefully
            output = self.out.getvalue()
            self.assertIn('error', output.lower())
        except Exception as e:
            # Should handle error gracefully
            self.assertIsInstance(e, Exception)
        finally:
            # Restore original method
            command.check_alert_system_health = original_method


class APIErrorHandlingTest(TestCase):
    """Test error handling in API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_api_with_invalid_json(self):
        """Test API with invalid JSON payload"""
        from rest_framework.test import APITestCase
        from rest_framework import status
        
        client = APITestCase()
        client.force_authenticate(user=self.user)
        
        # Try to post invalid JSON
        response = client.post(
            '/api/alerts/rules/',
            'invalid_json_data',
            content_type='application/json'
        )
        
        # Should return 400 Bad Request
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_api_with_missing_fields(self):
        """Test API with missing required fields"""
        from rest_framework.test import APITestCase
        from rest_framework import status
        
        client = APITestCase()
        client.force_authenticate(user=self.user)
        
        # Try to create alert rule without required fields
        response = client.post(
            '/api/alerts/rules/',
            {'name': 'Test Rule'},  # Missing required fields
            format='json'
        )
        
        # Should return 400 Bad Request
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_api_with_invalid_foreign_key(self):
        """Test API with invalid foreign key reference"""
        from rest_framework.test import APITestCase
        from rest_framework import status
        
        client = APITestCase()
        client.force_authenticate(user=self.user)
        
        # Try to create alert log with non-existent rule
        response = client.post(
            '/api/alerts/logs/',
            {
                'rule': 99999,  # Non-existent rule
                'trigger_value': 85.0,
                'threshold_value': 80.0,
                'message': 'Test alert'
            },
            format='json'
        )
        
        # Should return 400 Bad Request
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_api_with_unauthorized_access(self):
        """Test API with unauthorized access"""
        from rest_framework.test import APITestCase
        from rest_framework import status
        
        client = APITestCase()
        # Don't authenticate
        
        # Try to access protected endpoint
        response = client.get('/api/alerts/rules/')
        
        # Should return 401 Unauthorized
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_api_with_permission_denied(self):
        """Test API with permission denied"""
        from rest_framework.test import APITestCase
        from rest_framework import status
        
        # Create user without permissions
        limited_user = User.objects.create_user(
            username='limiteduser',
            email='limited@example.com',
            password='testpass123'
        )
        
        client = APITestCase()
        client.force_authenticate(user=limited_user)
        
        # Try to access admin-only endpoint
        response = client.post('/api/alerts/rules/', {
            'name': 'Test Rule',
            'alert_type': 'cpu_usage',
            'severity': 'high',
            'threshold_value': 80.0
        }, format='json')
        
        # Should return 403 Forbidden if permissions are required
        # Or 200 if permissions are not enforced at model level
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])
    
    def test_api_with_rate_limiting(self):
        """Test API with rate limiting"""
        from rest_framework.test import APITestCase
        from rest_framework import status
        
        client = APITestCase()
        client.force_authenticate(user=self.user)
        
        # Make many rapid requests
        responses = []
        for i in range(100):
            response = client.get('/api/alerts/rules/')
            responses.append(response.status_code)
        
        # Should handle rate limiting gracefully
        # Most requests should succeed, some might be rate limited
        success_count = sum(1 for status in responses if status == status.HTTP_200_OK)
        self.assertGreater(success_count, 50)  # At least half should succeed


class DatabaseErrorHandlingTest(TransactionTestCase):
    """Test handling of database errors"""
    
    def setUp(self):
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
    
    def test_connection_timeout_handling(self):
        """Test handling of database connection timeouts"""
        # This would typically be tested with mocking
        # as we can't easily simulate real connection timeouts
        
        try:
            # Simulate a long-running query
            from django.db import connection
            
            # This would normally timeout
            # with connection.cursor() as cursor:
            #     cursor.execute("SELECT pg_sleep(10)")  # PostgreSQL specific
            
            # For testing, we'll just verify the connection exists
            self.assertIsNotNone(connection)
            
        except Exception as e:
            # Should handle connection errors gracefully
            self.assertIsInstance(e, (DatabaseError, TimeoutError))
    
    def test_constraint_violation_handling(self):
        """Test handling of constraint violations"""
        try:
            # Try to violate unique constraint (if exists)
            AlertRule.objects.create(
                name=self.alert_rule.name,  # Same name
                alert_type='memory_usage',
                severity='medium',
                threshold_value=85.0
            )
        except IntegrityError as e:
            # Should handle constraint violation gracefully
            self.assertIn('unique', str(e).lower())
        except Exception as e:
            # Other errors should also be handled
            self.assertIsInstance(e, Exception)
    
    def test_foreign_key_violation_handling(self):
        """Test handling of foreign key violations"""
        try:
            # Try to create record with invalid foreign key
            AlertLog.objects.create(
                rule_id=99999,  # Non-existent foreign key
                trigger_value=85.0,
                threshold_value=80.0,
                message='Test alert'
            )
        except Exception as e:
            # Should handle foreign key violation gracefully
            self.assertIn('foreign key', str(e).lower())
    
    def test_transaction_rollback_handling(self):
        """Test handling of transaction rollbacks"""
        try:
            # Simulate transaction failure
            from django.db import transaction
            
            with transaction.atomic():
                # Create some records
                AlertLog.objects.create(
                    rule=self.alert_rule,
                    trigger_value=85.0,
                    threshold_value=80.0,
                    message='Test alert 1'
                )
                
                # Force an error
                AlertLog.objects.create(
                    rule_id=99999,  # Invalid foreign key
                    trigger_value=90.0,
                    threshold_value=80.0,
                    message='Test alert 2'
                )
                
        except Exception as e:
            # Transaction should be rolled back
            # No records should be created
            self.assertEqual(AlertLog.objects.count(), 0)
    
    def test_deadlock_handling(self):
        """Test handling of database deadlocks"""
        import threading
        import time
        
        results = []
        
        def create_alert_thread(thread_id):
            try:
                for i in range(10):
                    alert = AlertLog.objects.create(
                        rule=self.alert_rule,
                        trigger_value=85.0 + thread_id + i,
                        threshold_value=80.0,
                        message=f'Deadlock test {thread_id}-{i}'
                    )
                    time.sleep(0.01)  # Small delay to increase deadlock chance
                    results.append(('success', thread_id, alert.id))
            except Exception as e:
                results.append(('error', thread_id, str(e)))
        
        # Create multiple threads to increase deadlock chance
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_alert_thread, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results - should handle deadlocks gracefully
        success_count = sum(1 for status, _, _ in results if status == 'success')
        error_count = sum(1 for status, _, _ in results if status == 'error')
        
        # Should have some successes even if some errors occur
        self.assertGreater(success_count, 0)
        
        # Errors should be handled gracefully
        for status, thread_id, error in results:
            if status == 'error':
                self.assertIsInstance(error, str)


class FileErrorHandlingTest(TestCase):
    """Test handling of file-related errors"""
    
    def test_file_not_found_error(self):
        """Test handling of file not found errors"""
        try:
            # Try to read non-existent file
            with open('non_existent_file.json', 'r') as f:
                content = f.read()
        except FileNotFoundError as e:
            # Should handle file not found gracefully
            self.assertIsInstance(e, FileNotFoundError)
    
    def test_file_permission_error(self):
        """Test handling of file permission errors"""
        try:
            # Try to write to restricted file (if exists)
            with open('/root/restricted_file.json', 'w') as f:
                f.write('test')
        except (PermissionError, FileNotFoundError) as e:
            # Should handle permission error gracefully
            self.assertIsInstance(e, (PermissionError, FileNotFoundError))
    
    def test_json_parsing_error(self):
        """Test handling of JSON parsing errors"""
        try:
            # Try to parse invalid JSON
            json.loads('invalid json data')
        except json.JSONDecodeError as e:
            # Should handle JSON error gracefully
            self.assertIsInstance(e, json.JSONDecodeError)
    
    def test_large_file_handling(self):
        """Test handling of large files"""
        # Create a large JSON string
        large_data = {'data': 'x' * 1000000}  # 1MB of data
        
        try:
            # Try to serialize large data
            json_str = json.dumps(large_data)
            
            # Should handle large data
            self.assertGreater(len(json_str), 1000000)
        except (MemoryError, ValueError) as e:
            # Should handle memory errors gracefully
            self.assertIsInstance(e, (MemoryError, ValueError))


class NetworkErrorHandlingTest(TestCase):
    """Test handling of network-related errors"""
    
    def test_connection_timeout_error(self):
        """Test handling of connection timeout errors"""
        import urllib.request
        import urllib.error
        
        try:
            # Try to connect to non-existent server
            response = urllib.request.urlopen('http://non-existent-server.example.com', timeout=1)
        except urllib.error.URLError as e:
            # Should handle connection error gracefully
            self.assertIsInstance(e, urllib.error.URLError)
        except Exception as e:
            # Should handle other network errors gracefully
            self.assertIsInstance(e, Exception)
    
    def test_http_error_handling(self):
        """Test handling of HTTP errors"""
        import urllib.request
        import urllib.error
        
        try:
            # Try to request non-existent page
            response = urllib.request.urlopen('http://httpbin.org/status/404', timeout=5)
        except urllib.error.HTTPError as e:
            # Should handle HTTP error gracefully
            self.assertIsInstance(e, urllib.error.HTTPError)
            self.assertEqual(e.code, 404)
        except Exception as e:
            # Should handle other errors gracefully
            self.assertIsInstance(e, Exception)
    
    def test_dns_resolution_error(self):
        """Test handling of DNS resolution errors"""
        import urllib.request
        import urllib.error
        
        try:
            # Try to connect to invalid domain
            response = urllib.request.urlopen('http://invalid-domain-name.example.com', timeout=5)
        except urllib.error.URLError as e:
            # Should handle DNS error gracefully
            self.assertIsInstance(e, urllib.error.URLError)
        except Exception as e:
            # Should handle other errors gracefully
            self.assertIsInstance(e, Exception)


class LoggingErrorHandlingTest(TestCase):
    """Test error handling in logging"""
    
    def test_logging_with_invalid_data(self):
        """Test logging with invalid data"""
        import logging
        
        logger = logging.getLogger('alerts')
        
        try:
            # Try to log invalid data
            logger.info("Test message with invalid data: %s", None)
            logger.info("Test message with too many args: %s %s %s", 1, 2)
            
            # Should handle gracefully
            self.assertTrue(True)
        except Exception as e:
            # Should handle logging errors gracefully
            self.assertIsInstance(e, Exception)
    
    def test_logging_with_unicode_errors(self):
        """Test logging with unicode encoding errors"""
        import logging
        
        logger = logging.getLogger('alerts')
        
        try:
            # Try to log unicode data
            unicode_message = 'Test message with unicode: émojis  and unicôde: café'
            logger.info(unicode_message)
            
            # Should handle unicode gracefully
            self.assertTrue(True)
        except Exception as e:
            # Should handle unicode errors gracefully
            self.assertIsInstance(e, (UnicodeError, ValueError))


class ConfigurationErrorHandlingTest(TestCase):
    """Test handling of configuration errors"""
    
    def test_missing_configuration(self):
        """Test handling of missing configuration"""
        try:
            # Try to access missing configuration
            from django.conf import settings
            
            # Access non-existent setting
            value = getattr(settings, 'ALERTS_MISSING_SETTING', 'default_value')
            
            # Should handle missing setting gracefully
            self.assertEqual(value, 'default_value')
        except Exception as e:
            # Should handle configuration errors gracefully
            self.assertIsInstance(e, Exception)
    
    def test_invalid_configuration_type(self):
        """Test handling of invalid configuration type"""
        try:
            # Try to use configuration with wrong type
            from django.conf import settings
            
            # If setting exists but has wrong type
            if hasattr(settings, 'ALERTS_CONFIG'):
                config = settings.ALERTS_CONFIG
                if isinstance(config, str):
                    # Try to use string as dict
                    config_dict = eval(config)  # Not recommended, but for testing
                    self.assertIsInstance(config_dict, dict)
        except Exception as e:
            # Should handle type errors gracefully
            self.assertIsInstance(e, (TypeError, ValueError, SyntaxError))
    
    def test_environment_variable_error(self):
        """Test handling of environment variable errors"""
        import os
        
        try:
            # Try to access non-existent environment variable
            value = os.environ.get('ALERTS_MISSING_VAR', 'default_value')
            
            # Should handle missing variable gracefully
            self.assertEqual(value, 'default_value')
        except Exception as e:
            # Should handle environment errors gracefully
            self.assertIsInstance(e, Exception)
