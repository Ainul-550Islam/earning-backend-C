"""
Utility Tests

This module contains test cases for tenant management utility functions
including validators, helpers, and formatters.
"""

from django.test import TestCase
from django.utils import timezone
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from ..utils.validators import (
    TenantValidator, BillingValidator, SecurityValidator,
    AnalyticsValidator, BusinessValidator, DataValidator
)
from ..utils.helpers import (
    TenantHelper, DataHelper, SecurityHelper,
    NotificationHelper, CacheHelper
)
from ..utils.formatters import (
    TenantFormatter, BillingFormatter, SecurityFormatter,
    AnalyticsFormatter, DateTimeFormatter, TableFormatter
)


class TenantValidatorTests(TestCase):
    """Test cases for TenantValidator."""
    
    def test_validate_tenant_name_valid(self):
        """Test valid tenant name validation."""
        # Valid names
        valid_names = [
            'Test Tenant',
            'My-Tenant_123',
            'Company Name Inc.',
            'tenant-with-dashes'
        ]
        
        for name in valid_names:
            try:
                TenantValidator.validate_tenant_name(name)
            except ValidationError:
                self.fail(f"Valid name '{name}' raised ValidationError")
    
    def test_validate_tenant_name_invalid(self):
        """Test invalid tenant name validation."""
        # Invalid names
        invalid_names = [
            '',  # Empty
            'a',  # Too short
            'x' * 256,  # Too long
            'Tenant@123',  # Invalid characters
            'Tenant#123',  # Invalid characters
        ]
        
        for name in invalid_names:
            with self.assertRaises(ValidationError):
                TenantValidator.validate_tenant_name(name)
    
    def test_validate_slug_valid(self):
        """Test valid slug validation."""
        valid_slugs = [
            'test-tenant',
            'my-tenant-123',
            'company-name-inc',
            'tenant-with-dashes'
        ]
        
        for slug in valid_slugs:
            try:
                TenantValidator.validate_slug(slug)
            except ValidationError:
                self.fail(f"Valid slug '{slug}' raised ValidationError")
    
    def test_validate_slug_invalid(self):
        """Test invalid slug validation."""
        invalid_slugs = [
            '',  # Empty
            'ab',  # Too short
            'x' * 51,  # Too long
            'Test_Tenant',  # Uppercase
            'test--tenant',  # Double hyphens
            '-test-tenant',  # Leading hyphen
            'test-tenant-',  # Trailing hyphen
        ]
        
        for slug in invalid_slugs:
            with self.assertRaises(ValidationError):
                TenantValidator.validate_slug(slug)
    
    def test_validate_domain_valid(self):
        """Test valid domain validation."""
        valid_domains = [
            'example.com',
            'subdomain.example.com',
            'my-tenant.org',
            'test-site.net'
        ]
        
        for domain in valid_domains:
            try:
                TenantValidator.validate_domain(domain)
            except ValidationError:
                self.fail(f"Valid domain '{domain}' raised ValidationError")
    
    def test_validate_domain_invalid(self):
        """Test invalid domain validation."""
        invalid_domains = [
            'x' * 256,  # Too long
            'invalid-domain',
            'localhost',
            'test.com',  # Reserved
        ]
        
        for domain in invalid_domains:
            with self.assertRaises(ValidationError):
                TenantValidator.validate_domain(domain)


class BillingValidatorTests(TestCase):
    """Test cases for BillingValidator."""
    
    def test_validate_billing_cycle_valid(self):
        """Test valid billing cycle validation."""
        valid_cycles = ['monthly', 'yearly', 'quarterly']
        
        for cycle in valid_cycles:
            try:
                BillingValidator.validate_billing_cycle(cycle)
            except ValidationError:
                self.fail(f"Valid billing cycle '{cycle}' raised ValidationError")
    
    def test_validate_billing_cycle_invalid(self):
        """Test invalid billing cycle validation."""
        invalid_cycles = ['weekly', 'daily', 'invalid']
        
        for cycle in invalid_cycles:
            with self.assertRaises(ValidationError):
                BillingValidator.validate_billing_cycle(cycle)
    
    def test_validate_payment_method_valid(self):
        """Test valid payment method validation."""
        valid_methods = ['credit_card', 'bank_transfer', 'paypal', 'stripe', 'crypto']
        
        for method in valid_methods:
            try:
                BillingValidator.validate_payment_method(method)
            except ValidationError:
                self.fail(f"Valid payment method '{method}' raised ValidationError")
    
    def test_validate_payment_method_invalid(self):
        """Test invalid payment method validation."""
        invalid_methods = ['cash', 'check', 'invalid']
        
        for method in invalid_methods:
            with self.assertRaises(ValidationError):
                BillingValidator.validate_payment_method(method)
    
    def test_validate_invoice_amounts_valid(self):
        """Test valid invoice amounts validation."""
        # Valid amounts
        valid_combinations = [
            (100.0, 10.0, 5.0, 105.0),  # subtotal + tax - discount
            (50.0, 5.0, 0.0, 55.0),    # subtotal + tax
            (100.0, 0.0, 10.0, 90.0),   # subtotal - discount
        ]
        
        for subtotal, tax, discount, total in valid_combinations:
            try:
                BillingValidator.validate_invoice_amounts(subtotal, tax, discount, total)
            except ValidationError:
                self.fail(f"Valid amounts {subtotal}, {tax}, {discount}, {total} raised ValidationError")
    
    def test_validate_invoice_amounts_invalid(self):
        """Test invalid invoice amounts validation."""
        # Invalid amounts
        invalid_combinations = [
            (-100.0, 10.0, 5.0, -85.0),  # Negative subtotal
            (100.0, -10.0, 5.0, 95.0),   # Negative tax
            (100.0, 10.0, -5.0, 115.0),  # Negative discount
            (100.0, 10.0, 5.0, -85.0),   # Negative total
            (100.0, 10.0, 5.0, 100.0),   # Inconsistent calculation
        ]
        
        for subtotal, tax, discount, total in invalid_combinations:
            with self.assertRaises(ValidationError):
                BillingValidator.validate_invoice_amounts(subtotal, tax, discount, total)


class SecurityValidatorTests(TestCase):
    """Test cases for SecurityValidator."""
    
    def test_validate_password_strength_valid(self):
        """Test valid password strength validation."""
        valid_passwords = [
            'Password123!',
            'MySecurePass@2023',
            'Complex#Pass123',
            'Test1234$'
        ]
        
        for password in valid_passwords:
            try:
                SecurityValidator.validate_password_strength(password)
            except ValidationError:
                self.fail(f"Valid password '{password}' raised ValidationError")
    
    def test_validate_password_strength_invalid(self):
        """Test invalid password strength validation."""
        invalid_passwords = [
            '',  # Empty
            'short',  # Too short
            'x' * 129,  # Too long
            'password',  # No complexity
            '12345678',  # No complexity
            'PASSWORD',  # No complexity
        ]
        
        for password in invalid_passwords:
            with self.assertRaises(ValidationError):
                SecurityValidator.validate_password_strength(password)
    
    def test_validate_api_key_format_valid(self):
        """Test valid API key format validation."""
        valid_keys = [
            'tk_' + 'a' * 32,
            'tk_' + '1' * 32,
            'tk_' + 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6'
        ]
        
        for key in valid_keys:
            try:
                SecurityValidator.validate_api_key_format(key)
            except ValidationError:
                self.fail(f"Valid API key '{key}' raised ValidationError")
    
    def test_validate_api_key_format_invalid(self):
        """Test invalid API key format validation."""
        invalid_keys = [
            '',  # Empty
            'short',  # Too short
            'tk_' + 'a' * 31,  # Too short
            'invalid_key_with_special_chars!',
            'key_without_prefix'
        ]
        
        for key in invalid_keys:
            with self.assertRaises(ValidationError):
                SecurityValidator.validate_api_key_format(key)
    
    def test_validate_ip_address_valid(self):
        """Test valid IP address validation."""
        valid_ips = [
            '192.168.1.1',
            '10.0.0.1',
            '172.16.0.1',
            '127.0.0.1',
            '2001:db8::1'
        ]
        
        for ip in valid_ips:
            try:
                SecurityValidator.validate_ip_address(ip)
            except ValidationError:
                self.fail(f"Valid IP '{ip}' raised ValidationError")
    
    def test_validate_ip_address_invalid(self):
        """Test invalid IP address validation."""
        invalid_ips = [
            '',  # Empty
            '999.999.999.999',  # Invalid range
            '192.168.1',  # Incomplete
            'invalid_ip',
            '192.168.1.1.1'  # Too many parts
        ]
        
        for ip in invalid_ips:
            with self.assertRaises(ValidationError):
                SecurityValidator.validate_ip_address(ip)


class AnalyticsValidatorTests(TestCase):
    """Test cases for AnalyticsValidator."""
    
    def test_validate_metric_value_valid(self):
        """Test valid metric value validation."""
        valid_combinations = [
            (100, 'numeric'),
            (True, 'boolean'),
            ('text_value', 'text'),
            (75.5, 'percentage'),
        ]
        
        for value, metric_type in valid_combinations:
            try:
                AnalyticsValidator.validate_metric_value(value, metric_type)
            except ValidationError:
                self.fail(f"Valid value '{value}' for type '{metric_type}' raised ValidationError")
    
    def test_validate_metric_value_invalid(self):
        """Test invalid metric value validation."""
        invalid_combinations = [
            ('not_numeric', 'numeric'),
            ('not_boolean', 'boolean'),
            (123, 'text'),
            (-10, 'percentage'),  # Negative percentage
            (150, 'percentage'),  # Over 100%
        ]
        
        for value, metric_type in invalid_combinations:
            with self.assertRaises(ValidationError):
                AnalyticsValidator.validate_metric_value(value, metric_type)
    
    def test_validate_health_score_valid(self):
        """Test valid health score validation."""
        valid_scores = [0, 50, 75, 100, 85.5]
        
        for score in valid_scores:
            try:
                AnalyticsValidator.validate_health_score(score)
            except ValidationError:
                self.fail(f"Valid health score '{score}' raised ValidationError")
    
    def test_validate_health_score_invalid(self):
        """Test invalid health score validation."""
        invalid_scores = [-10, -1, 101, 150]
        
        for score in invalid_scores:
            with self.assertRaises(ValidationError):
                AnalyticsValidator.validate_health_score(score)
    
    def test_validate_feature_flag_rollout_valid(self):
        """Test valid feature flag rollout validation."""
        valid_rollouts = [0, 25, 50, 75, 100, 85.5]
        
        for rollout in valid_rollouts:
            try:
                AnalyticsValidator.validate_feature_flag_rollout(rollout)
            except ValidationError:
                self.fail(f"Valid rollout '{rollout}' raised ValidationError")
    
    def test_validate_feature_flag_rollout_invalid(self):
        """Test invalid feature flag rollout validation."""
        invalid_rollouts = [-10, -1, 101, 150]
        
        for rollout in invalid_rollouts:
            with self.assertRaises(ValidationError):
                AnalyticsValidator.validate_feature_flag_rollout(rollout)


class TenantHelperTests(TestCase):
    """Test cases for TenantHelper."""
    
    def test_generate_unique_slug(self):
        """Test unique slug generation."""
        name = "Test Tenant Name"
        existing_slugs = ["test-tenant-name", "test-tenant-name-2"]
        
        slug = TenantHelper.generate_unique_slug(name, existing_slugs)
        
        self.assertEqual(slug, "test-tenant-name-3")
    
    def test_generate_unique_slug_no_conflicts(self):
        """Test slug generation without conflicts."""
        name = "Test Tenant"
        existing_slugs = []
        
        slug = TenantHelper.generate_unique_slug(name, existing_slugs)
        
        self.assertEqual(slug, "test-tenant")
    
    def test_generate_api_key(self):
        """Test API key generation."""
        api_key = TenantHelper.generate_api_key()
        
        self.assertTrue(api_key.startswith('tk_'))
        self.assertEqual(len(api_key), 35)  # 'tk_' + 32 chars
    
    def test_generate_webhook_secret(self):
        """Test webhook secret generation."""
        secret = TenantHelper.generate_webhook_secret()
        
        self.assertTrue(len(secret) >= 32)
        self.assertIsInstance(secret, str)
    
    def test_format_currency(self):
        """Test currency formatting."""
        amount = 1234.56
        
        formatted = TenantHelper.format_currency(amount)
        self.assertIn('$1,234.56', formatted)
        
        formatted_eur = TenantHelper.format_currency(amount, 'EUR')
        self.assertIn('EUR 1,234.56', formatted_eur)
    
    def test_calculate_percentage(self):
        """Test percentage calculation."""
        percentage = TenantHelper.calculate_percentage(25, 100)
        self.assertEqual(percentage, 25.0)
        
        percentage = TenantHelper.calculate_percentage(1, 3, 2)
        self.assertEqual(percentage, 33.33)
        
        percentage = TenantHelper.calculate_percentage(10, 0)
        self.assertEqual(percentage, 0.0)
    
    def test_get_date_range(self):
        """Test date range calculation."""
        # Test daily
        start, end = TenantHelper.get_date_range('daily')
        self.assertEqual((end - start).days, 1)
        
        # Test weekly
        start, end = TenantHelper.get_date_range('weekly')
        self.assertEqual((end - start).days, 7)
        
        # Test monthly
        start, end = TenantHelper.get_date_range('monthly')
        self.assertTrue((end - start).days in [28, 29, 30, 31])
    
    def test_format_file_size(self):
        """Test file size formatting."""
        size = TenantHelper.format_file_size(1024)
        self.assertIn('1.0 KB', size)
        
        size = TenantHelper.format_file_size(1024 * 1024)
        self.assertIn('1.0 MB', size)
        
        size = TenantHelper.format_file_size(0)
        self.assertEqual(size, '0 B')
    
    def test_generate_invoice_number(self):
        """Test invoice number generation."""
        tenant_id = 123
        date = timezone.now()
        
        invoice_number = TenantHelper.generate_invoice_number(tenant_id, date)
        
        self.assertTrue(invoice_number.startswith('INV-'))
        self.assertIn(str(tenant_id), invoice_number)
    
    def test_calculate_trial_end_date(self):
        """Test trial end date calculation."""
        trial_end = TenantHelper.calculate_trial_end_date(14)
        
        expected = timezone.now() + timedelta(days=14)
        self.assertAlmostEqual(trial_end, expected, delta=timedelta(seconds=1))
    
    def test_is_trial_expired(self):
        """Test trial expiration check."""
        # Expired trial
        past_date = timezone.now() - timedelta(days=1)
        self.assertTrue(TenantHelper.is_trial_expired(past_date))
        
        # Active trial
        future_date = timezone.now() + timedelta(days=1)
        self.assertFalse(TenantHelper.is_trial_expired(future_date))
    
    def test_get_trial_days_remaining(self):
        """Test trial days remaining calculation."""
        # 5 days remaining
        future_date = timezone.now() + timedelta(days=5)
        self.assertEqual(TenantHelper.get_trial_days_remaining(future_date), 5)
        
        # Expired
        past_date = timezone.now() - timedelta(days=1)
        self.assertEqual(TenantHelper.get_trial_days_remaining(past_date), 0)


class DataHelperTests(TestCase):
    """Test cases for DataHelper."""
    
    def test_export_to_csv_empty_queryset(self):
        """Test CSV export with empty queryset."""
        from django.contrib.auth.models import User
        
        result = DataHelper.export_to_csv(User.objects.none())
        
        self.assertFalse(result['success'])
        self.assertIn('No data to export', result['message'])
    
    def test_export_to_json_empty_queryset(self):
        """Test JSON export with empty queryset."""
        from django.contrib.auth.models import User
        
        result = DataHelper.export_to_json(User.objects.none())
        
        self.assertFalse(result['success'])
        self.assertIn('No data to export', result['message'])
    
    def test_import_from_csv_invalid_json(self):
        """Test CSV import with invalid JSON."""
        invalid_json = 'invalid json content'
        
        result = DataHelper.import_from_json(invalid_json, object)
        
        self.assertFalse(result['success'])
        self.assertIn('Invalid JSON', result['message'])
    
    def test_import_from_json_not_array(self):
        """Test JSON import with non-array data."""
        not_array = '{"key": "value"}'
        
        result = DataHelper.import_from_json(not_array, object)
        
        self.assertFalse(result['success'])
        self.assertIn('must be an array', result['message'])


class SecurityHelperTests(TestCase):
    """Test cases for SecurityHelper."""
    
    def test_generate_secure_token(self):
        """Test secure token generation."""
        token = SecurityHelper.generate_secure_token()
        
        self.assertTrue(len(token) >= 32)
        self.assertIsInstance(token, str)
    
    def test_hash_data(self):
        """Test data hashing."""
        data = "test data"
        salt = "test salt"
        
        hashed = SecurityHelper.hash_data(data, salt)
        
        self.assertIsInstance(hashed, str)
        self.assertEqual(len(hashed), 64)  # SHA256 hex length
    
    def test_verify_hash(self):
        """Test hash verification."""
        data = "test data"
        salt = "test salt"
        
        hashed = SecurityHelper.hash_data(data, salt)
        is_valid = SecurityHelper.verify_hash(data, hashed, salt)
        
        self.assertTrue(is_valid)
        
        # Test with wrong data
        is_invalid = SecurityHelper.verify_hash("wrong data", hashed, salt)
        self.assertFalse(is_invalid)
    
    def test_mask_sensitive_info(self):
        """Test sensitive info masking."""
        sensitive = "1234567890123456"
        
        masked = SecurityHelper.mask_sensitive_info(sensitive, 4)
        
        self.assertTrue(masked.startswith('1234'))
        self.assertTrue(masked.endswith('3456'))
        self.assertIn('*', masked)
    
    def test_generate_csrf_token(self):
        """Test CSRF token generation."""
        token = SecurityHelper.generate_csrf_token()
        
        self.assertTrue(len(token) >= 32)
        self.assertIsInstance(token, str)


class TenantFormatterTests(TestCase):
    """Test cases for TenantFormatter."""
    
    def test_format_tenant_status(self):
        """Test tenant status formatting."""
        # Test active status
        status = TenantFormatter.format_tenant_status('active')
        self.assertEqual(status['label'], 'Active')
        self.assertEqual(status['color'], 'green')
        
        # Test suspended status
        status = TenantFormatter.format_tenant_status('suspended')
        self.assertEqual(status['label'], 'Suspended')
        self.assertEqual(status['color'], 'red')
        
        # Test unknown status
        status = TenantFormatter.format_tenant_status('unknown')
        self.assertEqual(status['label'], 'Unknown')
        self.assertEqual(status['color'], 'gray')
    
    def test_format_tenant_tier(self):
        """Test tenant tier formatting."""
        # Test basic tier
        tier = TenantFormatter.format_tenant_tier('basic')
        self.assertEqual(tier['label'], 'Basic')
        self.assertEqual(tier['color'], 'blue')
        
        # Test enterprise tier
        tier = TenantFormatter.format_tenant_tier('enterprise')
        self.assertEqual(tier['label'], 'Enterprise')
        self.assertEqual(tier['color'], 'gold')
    
    def test_format_trial_info(self):
        """Test trial information formatting."""
        from unittest.mock import Mock
        from django.utils import timezone
        
        tenant = Mock()
        tenant.trial_ends_at = timezone.now() + timedelta(days=5)
        
        trial_info = TenantFormatter.format_trial_info(tenant)
        
        self.assertIsNotNone(trial_info)
        self.assertEqual(trial_info['days_remaining'], 5)
        self.assertFalse(trial_info['is_expired'])


class BillingFormatterTests(TestCase):
    """Test cases for BillingFormatter."""
    
    def test_format_billing_status(self):
        """Test billing status formatting."""
        # Test active status
        status = BillingFormatter.format_billing_status('active')
        self.assertEqual(status['label'], 'Active')
        self.assertEqual(status['color'], 'green')
        
        # Test overdue status
        status = BillingFormatter.format_billing_status('overdue')
        self.assertEqual(status['label'], 'Overdue')
        self.assertEqual(status['color'], 'red')
    
    def test_format_invoice_status(self):
        """Test invoice status formatting."""
        # Test paid status
        status = BillingFormatter.format_invoice_status('paid')
        self.assertEqual(status['label'], 'Paid')
        self.assertEqual(status['color'], 'green')
        
        # Test pending status
        status = BillingFormatter.format_invoice_status('pending')
        self.assertEqual(status['label'], 'Pending')
        self.assertEqual(status['color'], 'blue')
    
    def test_format_currency(self):
        """Test currency formatting."""
        amount = 1234.56
        
        formatted = BillingFormatter.format_currency(amount)
        self.assertEqual(formatted['amount'], amount)
        self.assertEqual(formatted['currency'], 'USD')
        self.assertEqual(formatted['symbol'], '$')
        self.assertIn('1,234.56', formatted['formatted'])
    
    def test_calculate_days_overdue(self):
        """Test days overdue calculation."""
        from unittest.mock import Mock
        from django.utils import timezone
        
        # Test overdue invoice
        invoice = Mock()
        invoice.status = 'pending'
        invoice.due_date = timezone.now() - timedelta(days=5)
        
        days_overdue = BillingFormatter.calculate_days_overdue(invoice)
        self.assertEqual(days_overdue, 5)
        
        # Test paid invoice
        invoice.status = 'paid'
        days_overdue = BillingFormatter.calculate_days_overdue(invoice)
        self.assertEqual(days_overdue, 0)


class AnalyticsFormatterTests(TestCase):
    """Test cases for AnalyticsFormatter."""
    
    def test_format_metric_value(self):
        """Test metric value formatting."""
        # Test percentage
        formatted = AnalyticsFormatter.format_metric_value(75.5, 'percentage')
        self.assertEqual(formatted['unit'], '%')
        self.assertEqual(formatted['display'], '75.5%')
        
        # Test currency
        formatted = AnalyticsFormatter.format_metric_value(1234.56, 'currency')
        self.assertEqual(formatted['unit'], '$')
        self.assertIn('1,234.56', formatted['display'])
    
    def test_format_health_score(self):
        """Test health score formatting."""
        # Test excellent score
        formatted = AnalyticsFormatter.format_health_score(95)
        self.assertEqual(formatted['grade'], 'A+')
        self.assertEqual(formatted['color'], 'green')
        self.assertEqual(formatted['label'], 'Excellent')
        
        # Test poor score
        formatted = AnalyticsFormatter.format_health_score(45)
        self.assertEqual(formatted['grade'], 'F')
        self.assertEqual(formatted['color'], 'red')
        self.assertEqual(formatted['label'], 'Critical')
    
    def test_format_trend_direction(self):
        """Test trend direction formatting."""
        # Test upward trend
        trend = AnalyticsFormatter.format_trend_direction(100, 80)
        self.assertEqual(trend['direction'], 'up')
        self.assertEqual(trend['icon'], 'arrow-up')
        self.assertEqual(trend['color'], 'green')
        
        # Test downward trend
        trend = AnalyticsFormatter.format_trend_direction(80, 100)
        self.assertEqual(trend['direction'], 'down')
        self.assertEqual(trend['icon'], 'arrow-down')
        self.assertEqual(trend['color'], 'red')
    
    def test_format_bytes(self):
        """Test bytes formatting."""
        # Test kilobytes
        formatted = AnalyticsFormatter.format_bytes(1024)
        self.assertEqual(formatted, '1.0 KB')
        
        # Test megabytes
        formatted = AnalyticsFormatter.format_bytes(1024 * 1024)
        self.assertEqual(formatted, '1.0 MB')
        
        # Test zero bytes
        formatted = AnalyticsFormatter.format_bytes(0)
        self.assertEqual(formatted, '0 B')


class DateTimeFormatterTests(TestCase):
    """Test cases for DateTimeFormatter."""
    
    def test_format_datetime(self):
        """Test datetime formatting."""
        dt = timezone.now()
        
        # Test full format
        formatted = DateTimeFormatter.format_datetime(dt, 'full')
        self.assertIn(dt.strftime('%Y-%m-%d'), formatted)
        
        # Test date format
        formatted = DateTimeFormatter.format_datetime(dt, 'date')
        self.assertEqual(formatted, dt.strftime('%Y-%m-%d'))
        
        # Test time format
        formatted = DateTimeFormatter.format_datetime(dt, 'time')
        self.assertEqual(formatted, dt.strftime('%H:%M:%S'))
    
    def test_format_date(self):
        """Test date formatting."""
        date = timezone.now().date()
        
        # Test full format
        formatted = DateTimeFormatter.format_date(date, 'full')
        self.assertIn(date.strftime('%B'), formatted)
        
        # Test short format
        formatted = DateTimeFormatter.format_date(date, 'short')
        self.assertEqual(formatted, date.strftime('%m/%d/%Y'))
    
    def test_format_time_span(self):
        """Test time span formatting."""
        start = timezone.now()
        end = start + timedelta(days=2, hours=3, minutes=45)
        
        span = DateTimeFormatter.format_time_span(start, end)
        
        self.assertEqual(span['days'], 2)
        self.assertEqual(span['hours'], 3)
        self.assertEqual(span['minutes'], 45)
        self.assertIn('2d 3h 45m', span['display'])
    
    def test_format_age(self):
        """Test age formatting."""
        # Test today
        today = timezone.now()
        age = DateTimeFormatter.format_age(today)
        self.assertEqual(age['display'], 'Today')
        
        # Test yesterday
        yesterday = timezone.now() - timedelta(days=1)
        age = DateTimeFormatter.format_age(yesterday)
        self.assertEqual(age['display'], 'Yesterday')
        
        # Test days ago
        days_ago = timezone.now() - timedelta(days=5)
        age = DateTimeFormatter.format_age(days_ago)
        self.assertEqual(age['display'], '5 days ago')


class TableFormatterTests(TestCase):
    """Test cases for TableFormatter."""
    
    def test_format_table_data(self):
        """Test table data formatting."""
        data = [
            {'name': 'Test', 'status': 'active', 'amount': 100.50}
        ]
        
        columns = [
            {'key': 'name', 'label': 'Name'},
            {'key': 'status', 'label': 'Status', 'format': 'status'},
            {'key': 'amount', 'label': 'Amount', 'format': 'currency'}
        ]
        
        formatted = TableFormatter.format_table_data(data, columns)
        
        self.assertEqual(formatted['total_rows'], 1)
        self.assertEqual(len(formatted['columns']), 3)
        self.assertEqual(len(formatted['data']), 1)
        
        # Check formatted data
        row = formatted['data'][0]
        self.assertEqual(row['name'], 'Test')
        self.assertIsInstance(row['status'], dict)  # Status formatted
        self.assertIsInstance(row['amount'], dict)  # Currency formatted
    
    def test_format_summary_stats(self):
        """Test summary statistics formatting."""
        data = {'total_users': 150, 'revenue': 1234.56, 'growth': 25.5}
        
        stats_config = [
            {'key': 'total_users', 'label': 'Total Users', 'format': 'number'},
            {'key': 'revenue', 'label': 'Revenue', 'format': 'currency'},
            {'key': 'growth', 'label': 'Growth', 'format': 'percentage'}
        ]
        
        formatted = TableFormatter.format_summary_stats(data, stats_config)
        
        self.assertEqual(len(formatted), 3)
        
        # Check formatted stats
        total_users = next(s for s in formatted if s['key'] == 'total_users')
        self.assertEqual(total_users['formatted_value'], '150')
        
        revenue = next(s for s in formatted if s['key'] == 'revenue')
        self.assertIsInstance(revenue['formatted_value'], dict)
        
        growth = next(s for s in formatted if s['key'] == 'growth')
        self.assertIsInstance(growth['formatted_value'], dict)
