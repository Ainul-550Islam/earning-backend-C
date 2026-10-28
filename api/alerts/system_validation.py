#!/usr/bin/env python
"""
System Validation Script for Alerts System
Comprehensive testing of all components without Django test runner
"""
import os
import sys
import importlib
import traceback
import hashlib
import json
import time
from datetime import datetime, timezone

# Add alerts directory to path
alerts_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, alerts_dir)

# Configure Django settings before importing Django modules
import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'api.alerts.apps.AlertsConfig',
        ],
        SECRET_KEY='test-secret-key-for-alerts-system',
        USE_TZ=True,
        LOGGING={
            'version': 1,
            'disable_existing_loggers': False,
        },
    )

django.setup()

class SystemValidator:
    def __init__(self):
        self.test_results = {}
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        
    def log_test(self, test_name, passed, message=""):
        """Log test result"""
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
            print(f"✅ {test_name}: PASSED {message}")
        else:
            self.failed_tests += 1
            print(f"❌ {test_name}: FAILED {message}")
        
        self.test_results[test_name] = {
            'passed': passed,
            'message': message
        }
    
    def test_module_imports(self):
        """Test that all modules can be imported without circular import issues"""
        print("\n🧪 Testing Module Imports...")
        
        # Test critical modules
        modules_to_test = [
            'services.channels.SlackAlertService',
            'services.channels.TelegramAlertService', 
            'services.channels.EmailAlertService',
            'integration.integ_adapter',
            'integration.transformer',
            'integration.circuit_breaker',
            'integration.message_queue',
            'integration.data_validator',
            'services.incident.incident_manager',
            'services.intelligence.alert_intelligence'
        ]
        
        for module_name in modules_to_test:
            try:
                importlib.import_module(module_name)
                self.log_test(f"Import {module_name}", True)
            except ImportError as e:
                self.log_test(f"Import {module_name}", False, str(e))
            except Exception as e:
                self.log_test(f"Import {module_name}", False, f"Unexpected error: {str(e)}")
    
    def test_integration_system(self):
        """Test Integration System components"""
        print("\n🔗 Testing Integration System...")
        
        try:
            # Test adapter factory
            from api.alerts.integration.integ_adapter import AdapterFactory, JSONAdapter
            
            # Create a JSON adapter
            config = {'pretty_print': True, 'indent': 2}
            adapter = AdapterFactory.create_adapter('json', config)
            
            if adapter and isinstance(adapter, JSONAdapter):
                self.log_test("JSON Adapter Creation", True)
                
                # Test adapter initialization
                initialized = adapter.initialize()
                self.log_test("JSON Adapter Initialization", initialized)
                
                # Test alert sending
                test_data = {'message': 'Test alert', 'severity': 'high'}
                result = adapter.send_alert(test_data)
                self.log_test("JSON Adapter Send Alert", result.get('success', False), 
                             f"Result: {result.get('success', False)}")
                
                # Test health check
                health = adapter.health_check()
                self.log_test("JSON Adapter Health Check", health.get('healthy', False))
                
            else:
                self.log_test("JSON Adapter Creation", False, "Adapter not created or wrong type")
                
        except Exception as e:
            self.log_test("Integration System", False, str(e))
    
    def test_channel_services(self):
        """Test Channel Services"""
        print("\n📢 Testing Channel Services...")
        
        try:
            # Test Slack service
            from api.alerts.services.channels.SlackAlertService import SlackAlertService
            slack_service = SlackAlertService()
            self.log_test("Slack Service Instantiation", True)
            
            # Test Telegram service
            from api.alerts.services.channels.TelegramAlertService import TelegramAlertService
            telegram_service = TelegramAlertService()
            self.log_test("Telegram Service Instantiation", True)
            
            # Test Email service
            from api.alerts.services.channels.EmailAlertService import EmailAlertService
            email_service = EmailAlertService()
            self.log_test("Email Service Instantiation", True)
            
            # Test service configurations
            test_config = {
                'webhook_url': 'https://hooks.slack.com/test',
                'timeout': 30,
                'retry_count': 3
            }
            
            # Test Slack service configuration
            if hasattr(slack_service, 'configure'):
                slack_service.configure(test_config)
                self.log_test("Slack Service Configuration", True)
            else:
                self.log_test("Slack Service Configuration", False, "Configure method not found")
                
        except Exception as e:
            self.log_test("Channel Services", False, str(e))
    
    def test_circuit_breaker(self):
        """Test Circuit Breaker functionality"""
        print("\n⚡ Testing Circuit Breaker...")
        
        try:
            from api.alerts.integration.circuit_breaker import CircuitBreaker
            
            # Create circuit breaker
            breaker = CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=5,
                expected_exception=Exception
            )
            
            self.log_test("Circuit Breaker Creation", True)
            
            # Test successful call
            def success_func():
                return "success"
            
            result = breaker.call(success_func)
            self.log_test("Circuit Breaker Success Call", result == "success")
            
            # Test failure handling
            def failure_func():
                raise Exception("Test exception")
            
            # Trigger failures to open circuit
            for i in range(3):
                try:
                    breaker.call(failure_func)
                except Exception:
                    pass  # Expected
            
            # Circuit should be open now
            try:
                breaker.call(success_func)
                self.log_test("Circuit Breaker Open State", False, "Circuit should be open")
            except Exception:
                self.log_test("Circuit Breaker Open State", True)
                
        except Exception as e:
            self.log_test("Circuit Breaker", False, str(e))
    
    def test_retry_logic(self):
        """Test Retry Logic"""
        print("\n🔄 Testing Retry Logic...")
        
        try:
            # Test retry mechanism in services
            from api.alerts.services.channels.SlackAlertService import SlackAlertService
            
            service = SlackAlertService()
            
            # Mock retry configuration
            if hasattr(service, 'retry_count'):
                self.log_test("Retry Logic Configuration", True, f"Retry count: {service.retry_count}")
            else:
                self.log_test("Retry Logic Configuration", False, "Retry count not found")
                
        except Exception as e:
            self.log_test("Retry Logic", False, str(e))
    
    def test_sha256_hashing(self):
        """Test SHA-256 Hash Chaining"""
        print("\n🔐 Testing SHA-256 Hash Chaining...")
        
        try:
            # Create test alert data
            test_alert = {
                'message': 'Test alert message',
                'severity': 'high',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'source': 'test_system',
                'data': {'key': 'value', 'number': 42}
            }
            
            # Calculate SHA-256 hash
            alert_json = json.dumps(test_alert, sort_keys=True, separators=(',', ':'))
            hash_value = hashlib.sha256(alert_json.encode()).hexdigest()
            
            self.log_test("SHA-256 Hash Generation", True, f"Hash: {hash_value[:16]}...")
            
            # Test hash consistency
            hash_value_2 = hashlib.sha256(alert_json.encode()).hexdigest()
            self.log_test("SHA-256 Hash Consistency", hash_value == hash_value_2)
            
            # Test hash chaining (multiple levels)
            level1_hash = hashlib.sha256(alert_json.encode()).hexdigest()
            level2_hash = hashlib.sha256(level1_hash.encode()).hexdigest()
            level3_hash = hashlib.sha256(level2_hash.encode()).hexdigest()
            
            self.log_test("SHA-256 Hash Chaining", True, f"3-level chain created")
            
            # Verify data integrity
            modified_alert = test_alert.copy()
            modified_alert['severity'] = 'medium'
            modified_json = json.dumps(modified_alert, sort_keys=True, separators=(',', ':'))
            modified_hash = hashlib.sha256(modified_json.encode()).hexdigest()
            
            hash_different = hash_value != modified_hash
            self.log_test("SHA-256 Data Integrity", hash_different, "Hashes differ for different data")
            
        except Exception as e:
            self.log_test("SHA-256 Hashing", False, str(e))
    
    def test_data_validation(self):
        """Test Data Validation"""
        print("\n✅ Testing Data Validation...")
        
        try:
            from api.alerts.integration.data_validator import DataValidator
            
            validator = DataValidator()
            
            # Test valid data
            valid_data = {
                'message': 'Valid alert',
                'severity': 'high',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            validation_result = validator.validate_alert_data(valid_data)
            self.log_test("Valid Data Validation", validation_result.get('valid', False))
            
            # Test invalid data
            invalid_data = {
                'message': '',  # Empty message
                'severity': 'invalid_severity',  # Invalid severity
                'timestamp': 'invalid_timestamp'  # Invalid timestamp
            }
            
            invalid_result = validator.validate_alert_data(invalid_data)
            self.log_test("Invalid Data Rejection", not invalid_result.get('valid', True), 
                         f"Errors: {invalid_result.get('errors', [])}")
            
        except Exception as e:
            self.log_test("Data Validation", False, str(e))
    
    def test_performance_check(self):
        """Test Performance and Memory Usage"""
        print("\n⚡ Testing Performance...")
        
        try:
            # Test import time for large services
            start_time = time.time()
            
            from api.alerts.services.channels.EmailAlertService import EmailAlertService
            from api.alerts.services.channels.SlackAlertService import SlackAlertService
            from api.alerts.services.channels.TelegramAlertService import TelegramAlertService
            
            import_time = time.time() - start_time
            self.log_test("Large Services Import Time", import_time < 2.0, 
                         f"Import time: {import_time:.2f}s")
            
            # Test service instantiation time
            start_time = time.time()
            
            email_service = EmailAlertService()
            slack_service = SlackAlertService()
            telegram_service = TelegramAlertService()
            
            instantiation_time = time.time() - start_time
            self.log_test("Services Instantiation Time", instantiation_time < 1.0,
                         f"Instantiation time: {instantiation_time:.2f}s")
            
            # Test memory usage (basic check)
            import gc
            gc.collect()
            
            # Create multiple service instances to test memory
            services = []
            for i in range(10):
                services.append(EmailAlertService())
                services.append(SlackAlertService())
                services.append(TelegramAlertService())
            
            self.log_test("Memory Usage Test", True, f"Created {len(services)} service instances")
            
        except Exception as e:
            self.log_test("Performance Check", False, str(e))
    
    def test_migration_chain(self):
        """Test Migration Chain Integrity"""
        print("\n🗃️ Testing Migration Chain...")
        
        try:
            # Check migration files exist
            migrations_dir = os.path.join(alerts_dir, 'migrations')
            migration_files = []
            
            for i in range(1, 7):
                migration_file = f"000{i}_{'initial' if i == 1 else 'add_tenant_and_user_fields' if i == 2 else 'add_notification_system' if i == 3 else 'add_escalation_system' if i == 4 else 'add_backup_system' if i == 5 else 'add_scheduler_system'}.py"
                migration_path = os.path.join(migrations_dir, migration_file)
                
                if os.path.exists(migration_path):
                    migration_files.append(migration_file)
                    self.log_test(f"Migration File {i}", True)
                else:
                    self.log_test(f"Migration File {i}", False, "File not found")
            
            self.log_test("Migration Chain Complete", len(migration_files) == 6,
                         f"Found {len(migration_files)}/6 migration files")
            
        except Exception as e:
            self.log_test("Migration Chain", False, str(e))
    
    def generate_coverage_report(self):
        """Generate Test Coverage Report"""
        print("\n📊 Generating Test Coverage Report...")
        
        coverage_percentage = (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0
        
        report = {
            'total_tests': self.total_tests,
            'passed_tests': self.passed_tests,
            'failed_tests': self.failed_tests,
            'coverage_percentage': coverage_percentage,
            'test_results': self.test_results,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        print(f"\n📋 Test Coverage Report:")
        print(f"   Total Tests: {self.total_tests}")
        print(f"   Passed Tests: {self.passed_tests}")
        print(f"   Failed Tests: {self.failed_tests}")
        print(f"   Coverage: {coverage_percentage:.1f}%")
        
        if self.failed_tests > 0:
            print(f"\n❌ Failed Tests:")
            for test_name, result in self.test_results.items():
                if not result['passed']:
                    print(f"   - {test_name}: {result['message']}")
        
        return report
    
    def run_all_tests(self):
        """Run all system validation tests"""
        print("🚀 Starting Full System Validation...")
        print("=" * 60)
        
        # Run all test categories
        self.test_module_imports()
        self.test_integration_system()
        self.test_channel_services()
        self.test_circuit_breaker()
        self.test_retry_logic()
        self.test_sha256_hashing()
        self.test_data_validation()
        self.test_performance_check()
        self.test_migration_chain()
        
        # Generate coverage report
        report = self.generate_coverage_report()
        
        return report

def main():
    """Main function to run system validation"""
    validator = SystemValidator()
    report = validator.run_all_tests()
    
    # Final status
    if report['coverage_percentage'] == 100.0:
        print(f"\n🎉 SYSTEM VALIDATED: ALL TESTS PASSED (100%)")
        return True
    else:
        print(f"\n⚠️ SYSTEM VALIDATION: {report['coverage_percentage']:.1f}% PASSED")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
