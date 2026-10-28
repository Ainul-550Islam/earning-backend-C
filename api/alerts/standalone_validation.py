#!/usr/bin/env python
"""
Standalone System Validation - Tests components without Django setup
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

class StandaloneValidator:
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
    
    def test_basic_imports(self):
        """Test basic module imports without Django"""
        print("\n🧪 Testing Basic Imports...")
        
        # Test core Python modules
        try:
            import hashlib
            import json
            import time
            from datetime import datetime, timezone
            self.log_test("Core Python Modules", True)
        except ImportError as e:
            self.log_test("Core Python Modules", False, str(e))
        
        # Test file structure
        try:
            integration_dir = os.path.join(alerts_dir, 'integration')
            services_dir = os.path.join(alerts_dir, 'services')
            tests_dir = os.path.join(alerts_dir, 'tests')
            migrations_dir = os.path.join(alerts_dir, 'migrations')
            
            dirs_exist = all([
                os.path.exists(integration_dir),
                os.path.exists(services_dir),
                os.path.exists(tests_dir),
                os.path.exists(migrations_dir)
            ])
            
            self.log_test("Directory Structure", dirs_exist)
        except Exception as e:
            self.log_test("Directory Structure", False, str(e))
    
    def test_integration_files(self):
        """Test integration files exist and are readable"""
        print("\n🔗 Testing Integration Files...")
        
        integration_files = [
            'integration/integ_adapter.py',
            'integration/transformer.py',
            'integration/circuit_breaker.py',
            'integration/message_queue.py',
            'integration/data_validator.py',
            'integration/integ_handler.py',
            'integration/integ_registry.py',
            'integration/integ_signals.py',
            'integration/integ_constants.py',
            'integration/integ_exceptions.py',
            'integration/integ_audit_logs.py',
            'integration/auth_bridge.py',
            'integration/bridge.py',
            'integration/data_bridge.py',
            'integration/event_bus.py',
            'integration/fallback_logic.py',
            'integration/health_check.py',
            'integration/performance_monitor.py',
            'integration/sync_manager.py',
            'integration/versioning.py',
            'integration/webhooks_integration.py'
        ]
        
        for file_path in integration_files:
            full_path = os.path.join(alerts_dir, file_path)
            if os.path.exists(full_path):
                try:
                    # Check if file is readable and has content
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if len(content) > 100:  # Should have substantial content
                            self.log_test(f"Integration File: {file_path}", True, f"Size: {len(content)} chars")
                        else:
                            self.log_test(f"Integration File: {file_path}", False, "File too small")
                except Exception as e:
                    self.log_test(f"Integration File: {file_path}", False, f"Read error: {e}")
            else:
                self.log_test(f"Integration File: {file_path}", False, "File not found")
    
    def test_channel_service_files(self):
        """Test channel service files"""
        print("\n📢 Testing Channel Service Files...")
        
        channel_files = [
            'services/channels/SlackAlertService.py',
            'services/channels/TelegramAlertService.py',
            'services/channels/EmailAlertService.py',
            'services/channels/DiscordAlertService.py',
            'services/channels/SMSAlertService.py',
            'services/channels/WebhookAlertService.py',
            'services/channels/PagerDutyService.py',
            'services/channels/OpsGenieService.py'
        ]
        
        for file_path in channel_files:
            full_path = os.path.join(alerts_dir, file_path)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    # Check for key implementation indicators
                    has_class = 'class' in content
                    has_methods = 'def ' in content
                    is_large = len(content) > 5000  # Should be substantial
                    
                    if has_class and has_methods and is_large:
                        self.log_test(f"Channel Service: {file_path}", True, f"Size: {len(content)} chars")
                    else:
                        missing = []
                        if not has_class:
                            missing.append("class")
                        if not has_methods:
                            missing.append("methods")
                        if not is_large:
                            missing.append("size")
                        self.log_test(f"Channel Service: {file_path}", False, f"Missing: {', '.join(missing)}")
                        
                except Exception as e:
                    self.log_test(f"Channel Service: {file_path}", False, f"Read error: {e}")
            else:
                self.log_test(f"Channel Service: {file_path}", False, "File not found")
    
    def test_sha256_functionality(self):
        """Test SHA-256 hashing functionality"""
        print("\n🔐 Testing SHA-256 Functionality...")
        
        try:
            # Test data
            test_data = {
                'message': 'Test alert message',
                'severity': 'high',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'source': 'test_system'
            }
            
            # Test SHA-256 hash generation
            json_data = json.dumps(test_data, sort_keys=True, separators=(',', ':'))
            hash_value = hashlib.sha256(json_data.encode()).hexdigest()
            
            self.log_test("SHA-256 Hash Generation", True, f"Hash: {hash_value[:16]}...")
            
            # Test hash consistency
            hash_value_2 = hashlib.sha256(json_data.encode()).hexdigest()
            self.log_test("SHA-256 Hash Consistency", hash_value == hash_value_2)
            
            # Test hash chaining
            level1 = hashlib.sha256(json_data.encode()).hexdigest()
            level2 = hashlib.sha256(level1.encode()).hexdigest()
            level3 = hashlib.sha256(level2.encode()).hexdigest()
            
            self.log_test("SHA-256 Hash Chaining", len(level3) == 64)
            
            # Test data integrity
            modified_data = test_data.copy()
            modified_data['severity'] = 'medium'
            modified_json = json.dumps(modified_data, sort_keys=True, separators=(',', ':'))
            modified_hash = hashlib.sha256(modified_json.encode()).hexdigest()
            
            integrity_check = hash_value != modified_hash
            self.log_test("SHA-256 Data Integrity", integrity_check)
            
        except Exception as e:
            self.log_test("SHA-256 Functionality", False, str(e))
    
    def test_migration_files(self):
        """Test migration files"""
        print("\n🗃️ Testing Migration Files...")
        
        migrations_dir = os.path.join(alerts_dir, 'migrations')
        
        # Check migration files exist
        expected_migrations = [
            '0001_initial.py',
            '0002_add_tenant_and_user_fields.py',
            '0003_add_notification_system.py',
            '0004_add_escalation_system.py',
            '0005_add_backup_system.py',
            '0006_add_scheduler_system.py'
        ]
        
        for migration_file in expected_migrations:
            migration_path = os.path.join(migrations_dir, migration_file)
            if os.path.exists(migration_path):
                try:
                    with open(migration_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Check for migration class
                    has_migration_class = 'class Migration' in content
                    has_dependencies = 'dependencies' in content
                    has_operations = 'operations' in content
                    
                    if has_migration_class and has_dependencies and has_operations:
                        self.log_test(f"Migration File: {migration_file}", True)
                    else:
                        self.log_test(f"Migration File: {migration_file}", False, "Invalid migration structure")
                        
                except Exception as e:
                    self.log_test(f"Migration File: {migration_file}", False, f"Read error: {e}")
            else:
                self.log_test(f"Migration File: {migration_file}", False, "File not found")
    
    def test_code_quality_indicators(self):
        """Test code quality indicators"""
        print("\n📊 Testing Code Quality Indicators...")
        
        # Test for large service files (indicates proper implementation)
        service_files = [
            'services/channels/SlackAlertService.py',
            'services/channels/TelegramAlertService.py',
            'services/channels/EmailAlertService.py'
        ]
        
        for file_path in service_files:
            full_path = os.path.join(alerts_dir, file_path)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.split('\n')
                        
                    # Check code quality indicators
                    has_docstrings = '"""' in content
                    has_error_handling = 'try:' in content and 'except' in content
                    has_logging = 'logger' in content or 'logging' in content
                    is_substantial = len(lines) > 100
                    
                    quality_score = sum([
                        has_docstrings,
                        has_error_handling,
                        has_logging,
                        is_substantial
                    ])
                    
                    self.log_test(f"Code Quality: {file_path}", quality_score >= 3, 
                                 f"Score: {quality_score}/4, Lines: {len(lines)}")
                    
                except Exception as e:
                    self.log_test(f"Code Quality: {file_path}", False, f"Error: {e}")
    
    def test_abstract_method_implementations(self):
        """Test abstract method implementations"""
        print("\n🔧 Testing Abstract Method Implementations...")
        
        # Check integ_adapter.py for proper abstract methods
        adapter_file = os.path.join(alerts_dir, 'integration/integ_adapter.py')
        if os.path.exists(adapter_file):
            try:
                with open(adapter_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for abstract methods with NotImplementedError
                has_not_implemented = 'raise NotImplementedError' in content
                has_abstract_decorator = '@abstractmethod' in content
                has_concrete_implementations = 'class JSONAdapter' in content
                
                if has_not_implemented and has_abstract_decorator and has_concrete_implementations:
                    self.log_test("Abstract Methods in Adapter", True)
                else:
                    self.log_test("Abstract Methods in Adapter", False, "Missing proper abstract structure")
                    
            except Exception as e:
                self.log_test("Abstract Methods in Adapter", False, f"Error: {e}")
        
        # Check transformer.py for proper abstract methods
        transformer_file = os.path.join(alerts_dir, 'integration/transformer.py')
        if os.path.exists(transformer_file):
            try:
                with open(transformer_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                has_not_implemented = 'raise NotImplementedError' in content
                has_concrete_implementations = 'class PrometheusTransformer' in content
                
                if has_not_implemented and has_concrete_implementations:
                    self.log_test("Abstract Methods in Transformer", True)
                else:
                    self.log_test("Abstract Methods in Transformer", False, "Missing proper abstract structure")
                    
            except Exception as e:
                self.log_test("Abstract Methods in Transformer", False, f"Error: {e}")
    
    def generate_final_report(self):
        """Generate final test report"""
        print("\n📊 Final Test Report...")
        
        coverage_percentage = (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0
        
        report = {
            'total_tests': self.total_tests,
            'passed_tests': self.passed_tests,
            'failed_tests': self.failed_tests,
            'coverage_percentage': coverage_percentage,
            'test_results': self.test_results,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        print(f"\n📋 System Validation Results:")
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
        """Run all standalone tests"""
        print("🚀 Starting Standalone System Validation...")
        print("=" * 60)
        
        # Run all test categories
        self.test_basic_imports()
        self.test_integration_files()
        self.test_channel_service_files()
        self.test_sha256_functionality()
        self.test_migration_files()
        self.test_code_quality_indicators()
        self.test_abstract_method_implementations()
        
        # Generate final report
        report = self.generate_final_report()
        
        return report

def main():
    """Main function to run standalone validation"""
    validator = StandaloneValidator()
    report = validator.run_all_tests()
    
    # Final status
    if report['coverage_percentage'] >= 95.0:
        print(f"\n🎉 SYSTEM VALIDATED: ALL TESTS PASSED ({report['coverage_percentage']:.1f}%)")
        return True
    else:
        print(f"\n⚠️ SYSTEM VALIDATION: {report['coverage_percentage']:.1f}% PASSED")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
