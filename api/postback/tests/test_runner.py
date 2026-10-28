"""test_runner.py – Test runner configuration for postback module tests."""
import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner

if __name__ == "__main__":
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.base'
    django.setup()
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=False, failfast=False)
    
    # Test labels for new functionality
    test_labels = [
        'api.postback.tests.test_new_models',
        'api.postback.tests.test_new_services', 
        'api.postback.tests.test_new_api',
        'api.postback.tests.test_management_commands',
    ]
    
    failures = test_runner.run_tests(test_labels)
    
    if failures:
        sys.exit(1)
    else:
        print("\n✅ All postback module tests passed!")
        sys.exit(0)
