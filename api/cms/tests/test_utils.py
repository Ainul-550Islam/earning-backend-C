# cms/tests/test_utils.py
"""Test cases for CMS utilities."""
import pytest
import sys as _sys

class _LazyModel:
    """Lazy model proxy — resolves to actual Django model after setup."""
    def __init__(self, module, name):
        self._module = module
        self._name = name
        self._cls = None
    def _resolve(self):
        if self._cls is None:
            import importlib
            mod = importlib.import_module(self._module)
            self._cls = getattr(mod, self._name)
        return self._cls
    def __call__(self, *a, **kw): return self._resolve()(*a, **kw)
    def __getattr__(self, k):
        if k.startswith('_'): raise AttributeError(k)
        return getattr(self._resolve(), k)

# Lazy model proxies
Survey       = _LazyModel('api.cms.models_new.profile_surveys', 'SurveyTemplate')
Transaction  = _LazyModel('api.cms.models_new.survey_rewards', 'RewardTransaction')
SEOModel     = _LazyModel('api.cms.models_new.seo', 'SEOConfig')
UserProfile  = _LazyModel('api.cms.models_new.user_profile', 'UserProfile')
UserSegment  = _LazyModel('api.cms.models_new.user_profile', 'UserSegment')
TaskSchedule = _LazyModel('api.cms.models_new.task_management', 'TaskSchedule')
TaskExecution= _LazyModel('api.cms.models_new.task_management', 'TaskExecution')
TaskQueue    = _LazyModel('api.cms.models_new.task_management', 'TaskQueue')
VirtualCurrency      = _LazyModel('api.cms.models_new.cpalead', 'VirtualCurrency')
UserVirtualBalance   = _LazyModel('api.cms.models_new.cpalead', 'UserVirtualBalance')
ConversionLog        = _LazyModel('api.cms.models_new.cpalead', 'ConversionLog')
ClickLog             = _LazyModel('api.cms.models_new.cpalead', 'ClickLog')
ContentLocker        = _LazyModel('api.cms.models_new.cpalead', 'ContentLocker')
SurveyCompletion     = _LazyModel('api.cms.models_new.profile_surveys', 'SurveyCompletion')
SurveyCategory       = _LazyModel('api.cms.models_new.profile_surveys', 'SurveyCategory')
SurveyQuestion       = _LazyModel('api.cms.models_new.profile_surveys', 'SurveyQuestion')
SurveyReward         = _LazyModel('api.cms.models_new.survey_rewards', 'SurveyReward')
RewardPool           = _LazyModel('api.cms.models_new.survey_rewards', 'RewardPool')
Redirect301          = _LazyModel('api.cms.models_new.seo', 'Redirect301')
from decimal import Decimal
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple
from unittest.mock import patch, MagicMock, call

from api.cms.models_new.survey_rewards import SurveyReward, RewardTransaction as Transaction, RewardPool
from api.cms.models_new.seo import SEOConfig as SEOModel, Redirect301
from api.cms.models_new.user_profile import UserProfile, UserSegment
from api.cms.models_new.task_management import TaskSchedule, TaskExecution, TaskQueue
from api.cms.models_new.cpalead import VirtualCurrency, UserVirtualBalance, ConversionLog, ClickLog, ContentLocker
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple
from unittest.mock import patch, MagicMock, call
try:
    from api.cms.models_new.profile_surveys import (
        SurveyTemplate as Survey, SurveyCompletion, SurveyCategory, SurveyQuestion
    )
    from api.cms.models_new.survey_rewards import (
        SurveyReward, RewardTransaction as Transaction, RewardPool
    )
    from api.cms.models_new.seo import SEOConfig as SEOModel, Redirect301
    from api.cms.models_new.user_profile import UserProfile, UserSegment
    from api.cms.models_new.task_management import TaskSchedule, TaskExecution
    from api.cms.models_new.cpalead import (
        VirtualCurrency, UserVirtualBalance, ConversionLog, ClickLog, ContentLocker
    )
except Exception:
    pass
from django.test import TestCase
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from api.cms.utils import (
    StringUtils, DateUtils, NumberUtils, 
    ValidationUtils, SecurityUtils, utils
)


class TestStringUtils(TestCase):
    """Test string utilities."""
    
    def test_clean_string(self):
        """Test string cleaning."""
        # Test HTML removal
        html_text = "<p>Hello <b>World</b></p>"
        cleaned = StringUtils.clean_string(html_text)
        self.assertEqual(cleaned, "Hello World")
        
        # Test whitespace removal
        text_with_spaces = "Hello    World"
        cleaned_spaces = StringUtils.clean_string(text_with_spaces, remove_spaces=True)
        self.assertEqual(cleaned_spaces, "HelloWorld")
    
    def test_truncate_string(self):
        """Test string truncation."""
        long_text = "This is a very long string"
        truncated = StringUtils.truncate_string(long_text, 10)
        self.assertEqual(truncated, "This is...")
        
        # Test short string
        short_text = "Short"
        truncated_short = StringUtils.truncate_string(short_text, 10)
        self.assertEqual(truncated_short, "Short")
    
    def test_extract_emails(self):
        """Test email extraction."""
        text = "Contact us at test@example.com or admin@site.org"
        emails = StringUtils.extract_emails(text)
        self.assertIn("test@example.com", emails)
        self.assertIn("admin@site.org", emails)
    
    def test_is_valid_email(self):
        """Test email validation."""
        self.assertTrue(StringUtils.is_valid_email("test@example.com"))
        self.assertFalse(StringUtils.is_valid_email("invalid-email"))
        self.assertFalse(StringUtils.is_valid_email(""))
    
    def test_mask_sensitive_data(self):
        """Test data masking."""
        credit_card = "1234567890123456"
        masked = StringUtils.mask_sensitive_data(credit_card, visible_chars=4)
        self.assertEqual(masked, "************3456")
        
        short_data = "1234"
        masked_short = StringUtils.mask_sensitive_data(short_data, visible_chars=4)
        self.assertEqual(masked_short, "1234")


class TestDateUtils(TestCase):
    """Test date utilities."""
    
    def test_now_utc(self):
        """Test UTC time retrieval."""
        now = DateUtils.now_utc()
        self.assertIsNotNone(now)
        self.assertTrue(hasattr(now, 'tzinfo'))
    
    def test_get_time_ago(self):
        """Test time ago formatting."""
        now = timezone.now()
        
        # Test "Just now"
        recent = now - timedelta(seconds=30)
        time_ago = DateUtils.get_time_ago(recent)
        self.assertEqual(time_ago, "Just now")
        
        # Test "1 hour ago"
        hour_ago = now - timedelta(hours=1)
        time_ago_hour = DateUtils.get_time_ago(hour_ago)
        self.assertEqual(time_ago_hour, "1 hour ago")
        
        # Test "Never"
        time_ago_none = DateUtils.get_time_ago(None)
        self.assertEqual(time_ago_none, "Never")
    
    def test_parse_date_string(self):
        """Test date string parsing."""
        date_str = "2023-12-25"
        parsed = DateUtils.parse_date_string(date_str)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.year, 2023)
        self.assertEqual(parsed.month, 12)
        self.assertEqual(parsed.day, 25)
        
        # Test invalid date
        invalid_date = DateUtils.parse_date_string("invalid-date")
        self.assertIsNone(invalid_date)
    
    def test_get_date_range(self):
        """Test date range generation."""
        start, end = DateUtils.get_date_range('today')
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        self.assertGreater(end, start)
        
        start_week, end_week = DateUtils.get_date_range('week')
        self.assertIsNotNone(start_week)
        self.assertIsNotNone(end_week)


class TestNumberUtils(TestCase):
    """Test number utilities."""
    
    def test_safe_decimal(self):
        """Test safe decimal conversion."""
        # Test valid conversion
        result = NumberUtils.safe_decimal("123.45")
        self.assertEqual(result, Decimal("123.45"))
        
        # Test invalid conversion
        result_invalid = NumberUtils.safe_decimal("invalid", Decimal("0"))
        self.assertEqual(result_invalid, Decimal("0"))
        
        # Test None
        result_none = NumberUtils.safe_decimal(None, Decimal("10"))
        self.assertEqual(result_none, Decimal("10"))
    
    def test_format_currency(self):
        """Test currency formatting."""
        amount = 1234.56
        formatted = NumberUtils.format_currency(amount, 'USD')
        self.assertEqual(formatted, "USD 1,234.56")
        
        # Test zero
        formatted_zero = NumberUtils.format_currency(0, 'EUR')
        self.assertEqual(formatted_zero, "EUR 0.00")
    
    def test_calculate_percentage(self):
        """Test percentage calculation."""
        percentage = NumberUtils.calculate_percentage(25, 100)
        self.assertEqual(percentage, Decimal("25.00"))
        
        # Test zero division
        percentage_zero = NumberUtils.calculate_percentage(10, 0)
        self.assertEqual(percentage_zero, Decimal("0"))
    
    def test_round_decimal(self):
        """Test decimal rounding."""
        value = 3.14159
        rounded = NumberUtils.round_decimal(value, 2)
        self.assertEqual(rounded, Decimal("3.14"))
        
        rounded_0 = NumberUtils.round_decimal(value, 0)
        self.assertEqual(rounded_0, Decimal("3"))
    
    def test_is_positive_number(self):
        """Test positive number check."""
        self.assertTrue(NumberUtils.is_positive_number(10))
        self.assertTrue(NumberUtils.is_positive_number(0.1))
        self.assertFalse(NumberUtils.is_positive_number(0))
        self.assertFalse(NumberUtils.is_positive_number(-5))
        self.assertFalse(NumberUtils.is_positive_number("invalid"))


class TestValidationUtils(TestCase):
    """Test validation utilities."""
    
    def test_validate_username(self):
        """Test username validation."""
        # Valid username
        result_valid = ValidationUtils.validate_username("testuser123")
        self.assertTrue(result_valid['is_valid'])
        self.assertEqual(len(result_valid['errors']), 0)
        
        # Too short
        result_short = ValidationUtils.validate_username("ab")
        self.assertFalse(result_short['is_valid'])
        self.assertIn("Username must be at least 3 characters", result_short['errors'])
        
        # Invalid characters
        result_invalid = ValidationUtils.validate_username("test@user")
        self.assertFalse(result_invalid['is_valid'])
        self.assertIn("Username can only contain letters, numbers, and underscores", result_invalid['errors'])
    
    def test_validate_password_strength(self):
        """Test password strength validation."""
        # Strong password
        result_strong = ValidationUtils.validate_password_strength("StrongP@ss123")
        self.assertTrue(result_strong['is_valid'])
        self.assertEqual(result_strong['strength'], 'Strong')
        self.assertGreaterEqual(result_strong['score'], 4)
        
        # Weak password
        result_weak = ValidationUtils.validate_password_strength("weak")
        self.assertFalse(result_weak['is_valid'])
        self.assertEqual(result_weak['strength'], 'Very Weak')
        self.assertIn("Password must be at least 8 characters", result_weak['errors'])
    
    def test_validate_phone_number(self):
        """Test phone number validation."""
        # Valid US phone
        result_valid = ValidationUtils.validate_phone_number("1234567890", "US")
        self.assertTrue(result_valid['is_valid'])
        self.assertEqual(result_valid['formatted'], "(123) 456-7890")
        
        # Invalid phone
        result_invalid = ValidationUtils.validate_phone_number("123", "US")
        self.assertFalse(result_invalid['is_valid'])
        self.assertIn("US phone number must have 10 digits", result_invalid['errors'])


class TestSecurityUtils(TestCase):
    """Test security utilities."""
    
    def test_generate_csrf_token(self):
        """Test CSRF token generation."""
        token1 = SecurityUtils.generate_csrf_token()
        token2 = SecurityUtils.generate_csrf_token()
        
        self.assertNotEqual(token1, token2)
        self.assertEqual(len(token1), 43)  # URL-safe base64 length
    
    def test_generate_nonce(self):
        """Test nonce generation."""
        nonce1 = SecurityUtils.generate_nonce()
        nonce2 = SecurityUtils.generate_nonce()
        
        self.assertNotEqual(nonce1, nonce2)
        self.assertEqual(len(nonce1), 32)  # Hex length
    
    def test_secure_compare(self):
        """Test secure string comparison."""
        # Test equal strings
        self.assertTrue(SecurityUtils.secure_compare("test", "test"))
        
        # Test different strings
        self.assertFalse(SecurityUtils.secure_compare("test", "different"))
    
    def test_generate_session_id(self):
        """Test session ID generation."""
        session1 = SecurityUtils.generate_session_id()
        session2 = SecurityUtils.generate_session_id()
        
        self.assertNotEqual(session1, session2)
        self.assertEqual(len(session1), 43)  # URL-safe base64 length


class TestUtilityManager(TestCase):
    """Test utility manager."""
    
    def test_utility_manager_access(self):
        """Test utility manager access."""
        self.assertIsNotNone(utils.string)
        self.assertIsNotNone(utils.date)
        self.assertIsNotNone(utils.number)
        self.assertIsNotNone(utils.validation)
        self.assertIsNotNone(utils.security)
        
        # Test accessing specific utility
        self.assertEqual(utils.string.clean_string("test"), "test")
        self.assertEqual(utils.number.safe_decimal("123.45"), Decimal("123.45"))
    
    def test_get_utility(self):
        """Test getting utility by name."""
        string_util = utils.get_utility("string")
        self.assertEqual(string_util, StringUtils)
        
        # Test invalid utility
        invalid_util = utils.get_utility("nonexistent")
        self.assertIsNone(invalid_util)


class TestUtilityIntegration(TestCase):
    """Test utility integration."""
    
    def test_email_validation_and_cleaning(self):
        """Test email validation with string cleaning."""
        dirty_email = "  test@example.com  "
        cleaned = StringUtils.clean_string(dirty_email)
        is_valid = StringUtils.is_valid_email(cleaned)
        
        self.assertTrue(is_valid)
        self.assertEqual(cleaned, "test@example.com")
    
    def test_phone_normalization_and_validation(self):
        """Test phone normalization and validation."""
        # Test with various formats
        phone_formats = [
            "(123) 456-7890",
            "123-456-7890",
            "123.456.7890",
            "+1 (123) 456-7890"
        ]
        
        for phone in phone_formats:
            normalized = StringUtils.normalize_phone(phone)
            result = ValidationUtils.validate_phone_number(normalized, "US")
            
            self.assertTrue(result['is_valid'])
            self.assertEqual(result['formatted'], "(123) 456-7890")
    
    def test_currency_and_percentage_calculation(self):
        """Test currency formatting with percentage calculation."""
        amount = Decimal("1234.56")
        total = Decimal("10000.00")
        
        # Calculate percentage
        percentage = NumberUtils.calculate_percentage(amount, total)
        self.assertEqual(percentage, Decimal("12.35"))
        
        # Format as currency and percentage
        formatted_currency = NumberUtils.format_currency(amount)
        formatted_percentage = NumberUtils.format_percentage(percentage)
        
        self.assertEqual(formatted_currency, "USD 1,234.56")
        self.assertEqual(formatted_percentage, "12.35%")
    
    def test_date_formatting_and_time_ago(self):
        """Test date formatting with time ago."""
        now = timezone.now()
        past_time = now - timedelta(hours=2, minutes=30)
        
        # Format date
        formatted = DateUtils.format_datetime(past_time)
        self.assertIsNotNone(formatted)
        
        # Get time ago
        time_ago = DateUtils.get_time_ago(past_time)
        self.assertEqual(time_ago, "2 hours ago")
    
    def test_secure_token_generation_and_comparison(self):
        """Test secure token generation and comparison."""
        # Generate tokens
        token1 = SecurityUtils.generate_csrf_token()
        token2 = SecurityUtils.generate_csrf_token()
        
        # Test they're different
        self.assertFalse(SecurityUtils.secure_compare(token1, token2))
        
        # Test they match themselves
        self.assertTrue(SecurityUtils.secure_compare(token1, token1))
        
        # Test length and format
        self.assertGreater(len(token1), 40)
        self.assertTrue(all(c.isalnum() or c in '-_' for c in token1))


@pytest.mark.django_db
class TestUtilitiesWithModels(TestCase):
    """Test utilities with Django models."""
    
    def setUp(self):
        """Set up test data."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_user_data_processing(self):
        """Test user data processing with utilities."""
        # Test profile data cleaning
        profile_data = {
            'bio': '<script>alert("xss")</script>Clean bio',
            'phone': '(123) 456-7890',
            'email': '  test@example.com  '
        }
        
        cleaned_bio = StringUtils.clean_string(profile_data['bio'])
        self.assertEqual(cleaned_bio, 'alert("xss")Clean bio')
        
        normalized_phone = StringUtils.normalize_phone(profile_data['phone'])
        self.assertEqual(normalized_phone, '1234567890')
        
        cleaned_email = StringUtils.clean_string(profile_data['email'])
        self.assertTrue(StringUtils.is_valid_email(cleaned_email))
    
    def test_timestamp_processing(self):
        """Test timestamp processing with utilities."""
        from django.utils import timezone
        
        # Get current time and process
        now = timezone.now()
        formatted = DateUtils.format_datetime(now)
        time_ago = DateUtils.get_time_ago(now - timedelta(hours=1))
        
        self.assertIsNotNone(formatted)
        self.assertEqual(time_ago, "1 hour ago")
