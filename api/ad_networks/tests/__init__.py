"""
api/ad_networks/tests package
"""

# Test configuration
import os
import sys

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Django settings for tests
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')

# Import Django
import django
django.setup()

# Test constants
TEST_TENANT_ID = 'test_tenant_123'
TEST_USER_EMAIL = 'test@example.com'
TEST_ADMIN_EMAIL = 'admin@example.com'

__all__ = [
    'TEST_TENANT_ID',
    'TEST_USER_EMAIL',
    'TEST_ADMIN_EMAIL'
]
