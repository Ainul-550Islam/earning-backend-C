"""
Helper functions for tests.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
import random
import string

from django.core.files.uploadedfile import SimpleUploadedFile


def create_test_image(filename='test.jpg'):
    """Create a dummy image file for testing."""
    return SimpleUploadedFile(
        filename,
        b'fake_image_content',
        content_type='image/jpeg'
    )


def create_test_pdf(filename='test.pdf'):
    """Create a dummy PDF file for testing."""
    return SimpleUploadedFile(
        filename,
        b'%PDF-1.4 fake pdf content',
        content_type='application/pdf'
    )


def random_string(length=10):
    """Generate a random string of fixed length."""
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))


def random_email():
    """Generate a random email."""
    return f'{random_string()}@example.com'


def random_phone():
    """Generate a random phone number."""
    return '+1' + ''.join(str(random.randint(0, 9)) for _ in range(10))


def future_date(days=7):
    """Return a date in the future."""
    return datetime.now() + timedelta(days=days)


def past_date(days=7):
    """Return a date in the past."""
    return datetime.now() - timedelta(days=days)


def assert_decimal_equal(decimal1, decimal2, places=2):
    """Assert that two decimals are equal up to certain places."""
    if isinstance(decimal1, str):
        decimal1 = Decimal(decimal1)
    if isinstance(decimal2, str):
        decimal2 = Decimal(decimal2)
    
    rounded1 = round(decimal1, places)
    rounded2 = round(decimal2, places)
    
    assert rounded1 == rounded2, f"{rounded1} != {rounded2}"


def assert_datetime_approx(dt1, dt2, tolerance_seconds=5):
    """Assert that two datetimes are approximately equal."""
    diff = abs((dt1 - dt2).total_seconds())
    assert diff <= tolerance_seconds, f"DateTime difference {diff}s > {tolerance_seconds}s"


def print_response(response):
    """Pretty print response for debugging."""
    print(f"Status: {response.status_code}")
    print("Headers:")
    for key, value in response.items():
        print(f"  {key}: {value}")
    print("Body:")
    try:
        print(json.dumps(response.data, indent=2))
    except:
        print(response.content)