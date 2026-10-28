#!/usr/bin/env python
# ALERTS MODULE - TEST RUNNER SCRIPT
# File: test_runner.py

import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner
import logging

logger = logging.getLogger(__name__)


def run_tests():
    """
    Run all tests for the alerts module
    """
    
    print("\n" + "="*80)
    print("🧪 ALERTS MODULE - COMPLETE TEST SUITE RUNNER")
    print("="*80 + "\n")
    
    # Configure Django
    os.environ['DJANGO_SETTINGS_MODULE'] = 'alerts.settings'
    django.setup()
    
    # Get test runner
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=True, keepdb=True)
    
    # Test groups
    test_groups = {
        'SERVICE TESTS': [
            'api.alerts.tests.test_services_consolidated.AlertProcessingServiceTest',
            'api.alerts.tests.test_services_consolidated.SystemHealthServiceTest',
            'api.alerts.tests.test_services_consolidated.ConfigurationServiceTest',
            'api.alerts.tests.test_services_consolidated.PerformanceServiceTest',
            'api.alerts.tests.test_services_consolidated.MaintenanceServiceTest',
            'api.alerts.tests.test_services_consolidated.TestingServiceTest',
            'api.alerts.tests.test_services_consolidated.EventServiceTest',
            'api.alerts.tests.test_services_consolidated.RegistryServiceTest',
            'api.alerts.tests.test_services_consolidated.StatisticsServiceTest',
            'api.alerts.tests.test_services_consolidated.RateLimitingServiceTest',
        ],
        'ALL TESTS': [
            'api.alerts.tests.test_services_consolidated',
        ]
    }
    
    print("\n📋 AVAILABLE TEST SUITES:\n")
    print("1. SERVICE TESTS (Individual service tests)")
    print("2. ALL TESTS (Complete test suite)\n")
    
    # Run all tests
    print("Running complete test suite...\n")
    failures = test_runner.run_tests(['api.alerts.tests.test_services_consolidated'])
    
    print("\n" + "="*80)
    if failures:
        print(f"❌ TESTS FAILED: {failures} failures")
    else:
        print("✅ ALL TESTS PASSED!")
    print("="*80 + "\n")
    
    return failures


def run_specific_test(test_name):
    """
    Run a specific test
    """
    os.environ['DJANGO_SETTINGS_MODULE'] = 'alerts.settings'
    django.setup()
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=True, keepdb=True)
    
    failures = test_runner.run_tests([test_name])
    return failures


def coverage_report():
    """
    Generate coverage report
    """
    print("\n" + "="*80)
    print("📊 TEST COVERAGE REPORT")
    print("="*80 + "\n")
    
    try:
        import coverage
        
        # Start coverage
        cov = coverage.Coverage()
        cov.start()
        
        # Run tests
        os.environ['DJANGO_SETTINGS_MODULE'] = 'alerts.settings'
        django.setup()
        
        TestRunner = get_runner(settings)
        test_runner = TestRunner(verbosity=0, interactive=False)
        test_runner.run_tests(['api.alerts.tests.test_services_consolidated'])
        
        # Stop coverage
        cov.stop()
        cov.save()
        
        # Generate report
        print("\nCoverage by Service:\n")
        cov.report(include=['alerts/services/*'])
        
        # Generate HTML report
        cov.html_report(directory='htmlcov')
        print("\n✅ HTML coverage report generated in htmlcov/")
        
    except ImportError:
        print("❌ Coverage module not installed: pip install coverage")


if __name__ == '__main__':
    
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Run Alerts Module Tests'
    )
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Generate coverage report'
    )
    parser.add_argument(
        '--test',
        type=str,
        help='Run specific test (e.g., api.alerts.tests.test_services_consolidated.AlertProcessingServiceTest)'
    )
    
    args = parser.parse_args()
    
    if args.coverage:
        coverage_report()
    elif args.test:
        failures = run_specific_test(args.test)
        sys.exit(failures)
    else:
        failures = run_tests()
        sys.exit(failures)
