"""
tasks/tests/test_utils.py
Comprehensive test suite for utility functions.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import json


class TestSecurityUtilities:
    """Test security utility functions"""
    
    def test_generate_secure_token(self):
        """Test secure token generation"""
        from api.tasks.utils import generate_secure_token
        
        token1 = generate_secure_token()
        token2 = generate_secure_token()
        
        assert isinstance(token1, str)
        assert isinstance(token2, str)
        assert len(token1) > 0
        assert len(token2) > 0
        assert token1 != token2  # Should be unique
    
    def test_generate_secure_token_custom_length(self):
        """Test secure token generation with custom length"""
        from api.tasks.utils import generate_secure_token
        
        token = generate_secure_token(16)
        assert len(token) >= 16
    
    def test_hash_sensitive_data(self):
        """Test sensitive data hashing"""
        from api.tasks.utils import hash_sensitive_data
        
        data = "sensitive_info"
        hash1 = hash_sensitive_data(data)
        hash2 = hash_sensitive_data(data)
        
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA256 hex length
        assert hash1 == hash2  # Same input should produce same hash
    
    def test_hash_sensitive_data_with_salt(self):
        """Test hashing with custom salt"""
        from api.tasks.utils import hash_sensitive_data
        
        data = "sensitive_info"
        salt = "custom_salt"
        hash1 = hash_sensitive_data(data, salt)
        hash2 = hash_sensitive_data(data, salt)
        
        assert hash1 == hash2
    
    def test_validate_email_format_valid(self):
        """Test email validation with valid emails"""
        from api.tasks.utils import validate_email_format
        
        valid_emails = [
            "user@example.com",
            "test.email+tag@domain.co.uk",
            "user123@test-domain.org",
            "firstname.lastname@company.com"
        ]
        
        for email in valid_emails:
            assert validate_email_format(email) is True
    
    def test_validate_email_format_invalid(self):
        """Test email validation with invalid emails"""
        from api.tasks.utils import validate_email_format
        
        invalid_emails = [
            "invalid-email",
            "@missing-local.com",
            "user@.com",
            "user@domain.",
            "user space@domain.com",
            "user@domain..com"
        ]
        
        for email in invalid_emails:
            assert validate_email_format(email) is False
    
    def test_sanitize_phone_number(self):
        """Test phone number sanitization"""
        from api.tasks.utils import sanitize_phone_number
        
        test_cases = [
            ("+1 (555) 123-4567", "15551234567"),
            ("(555) 123-4567", "5551234567"),
            ("555.123.4567", "5551234567"),
            ("5551234567", "5551234567"),
            ("+44 20 7946 0958", "442079460958")
        ]
        
        for input_phone, expected in test_cases:
            result = sanitize_phone_number(input_phone)
            assert result == expected
    
    def test_mask_sensitive_info(self):
        """Test sensitive info masking"""
        from api.tasks.utils import mask_sensitive_info
        
        # Test credit card masking
        card = "4111111111111111"
        masked = mask_sensitive_info(card, '*', 4)
        assert masked == "************1111"
        
        # Test short string
        short = "123"
        masked_short = mask_sensitive_info(short, '*', 4)
        assert masked_short == "123"


class TestDataValidationUtilities:
    """Test data validation utilities"""
    
    def test_safe_decimal_valid(self):
        """Test safe decimal conversion with valid input"""
        from api.tasks.utils import safe_decimal
        
        test_cases = [
            ("123.45", Decimal("123.45")),
            (123, Decimal("123")),
            (Decimal("99.99"), Decimal("99.99")),
            (None, Decimal("0"))
        ]
        
        for input_val, expected in test_cases:
            result = safe_decimal(input_val)
            assert result == expected
    
    def test_safe_decimal_invalid(self):
        """Test safe decimal conversion with invalid input"""
        from api.tasks.utils import safe_decimal
        
        invalid_inputs = ["invalid", {}, [], object()]
        
        for input_val in invalid_inputs:
            result = safe_decimal(input_val)
            assert result == Decimal("0")
    
    def test_safe_int_valid(self):
        """Test safe integer conversion with valid input"""
        from api.tasks.utils import safe_int
        
        test_cases = [
            ("123", 123),
            (123.45, 123),
            (123, 123),
            (None, 0)
        ]
        
        for input_val, expected in test_cases:
            result = safe_int(input_val)
            assert result == expected
    
    def test_safe_int_invalid(self):
        """Test safe integer conversion with invalid input"""
        from api.tasks.utils import safe_int
        
        invalid_inputs = ["invalid", {}, [], object()]
        
        for input_val in invalid_inputs:
            result = safe_int(input_val)
            assert result == 0
    
    def test_safe_float_valid(self):
        """Test safe float conversion with valid input"""
        from api.tasks.utils import safe_float
        
        test_cases = [
            ("123.45", 123.45),
            (123, 123.0),
            (123.45, 123.45),
            (None, 0.0)
        ]
        
        for input_val, expected in test_cases:
            result = safe_float(input_val)
            assert abs(result - expected) < 0.001
    
    def test_safe_bool_valid(self):
        """Test safe boolean conversion with valid input"""
        from api.tasks.utils import safe_bool
        
        test_cases = [
            (True, True),
            (False, False),
            ("true", True),
            ("yes", True),
            ("1", True),
            ("on", True),
            ("enabled", True),
            ("false", False),
            ("no", False),
            ("0", False),
            ("off", False),
            (1, True),
            (0, False),
            (None, False)
        ]
        
        for input_val, expected in test_cases:
            result = safe_bool(input_val)
            assert result == expected
    
    def test_safe_json_loads_valid(self):
        """Test safe JSON loading with valid input"""
        from api.tasks.utils import safe_json_loads
        
        valid_json = '{"key": "value", "number": 123}'
        result = safe_json_loads(valid_json)
        
        assert result == {"key": "value", "number": 123}
    
    def test_safe_json_loads_invalid(self):
        """Test safe JSON loading with invalid input"""
        from api.tasks.utils import safe_json_loads
        
        invalid_json = '{"invalid": json}'
        result = safe_json_loads(invalid_json, {"default": True})
        
        assert result == {"default": True}
    
    def test_safe_json_dumps_valid(self):
        """Test safe JSON dumping with valid input"""
        from api.tasks.utils import safe_json_dumps
        
        data = {"key": "value", "number": 123}
        result = safe_json_dumps(data)
        
        assert json.loads(result) == data
    
    def test_safe_json_dumps_invalid(self):
        """Test safe JSON dumping with invalid input"""
        from api.tasks.utils import safe_json_dumps
        
        invalid_data = object()  # Not JSON serializable
        result = safe_json_dumps(invalid_data, "{}")
        
        assert result == "{}"


class TestDateTimeUtilities:
    """Test date/time utility functions"""
    
    def test_parse_iso_datetime_valid(self):
        """Test ISO datetime parsing with valid inputs"""
        from api.tasks.utils import parse_iso_datetime
        
        test_cases = [
            ("2023-12-25T10:30:00Z", datetime(2023, 12, 25, 10, 30, tzinfo=timezone.utc)),
            ("2023-12-25T10:30:00.123456Z", datetime(2023, 12, 25, 10, 30, 0, 123456, tzinfo=timezone.utc)),
            ("2023-12-25T10:30:00", datetime(2023, 12, 25, 10, 30)),
            ("2023-12-25", datetime(2023, 12, 25)),
            (None, None),
            ("", None)
        ]
        
        for input_str, expected in test_cases:
            result = parse_iso_datetime(input_str)
            assert result == expected
    
    def test_parse_iso_datetime_invalid(self):
        """Test ISO datetime parsing with invalid inputs"""
        from api.tasks.utils import parse_iso_datetime
        
        invalid_inputs = ["not-a-date", "2023-13-45", "invalid"]
        
        for input_str in invalid_inputs:
            result = parse_iso_datetime(input_str)
            assert result is None
    
    def test_format_duration(self):
        """Test duration formatting"""
        from api.tasks.utils import format_duration
        
        test_cases = [
            (30, "30.0s"),
            (90, "1.5m"),
            (3600, "1.0h"),
            (86400, "1.0d"),
            (90061, "1.0d")  # Just over 1 day
        ]
        
        for seconds, expected in test_cases:
            result = format_duration(seconds)
            assert expected in result  # Should contain the unit
    
    def test_get_time_range(self):
        """Test time range generation"""
        from api.tasks.utils import get_time_range
        from datetime import timedelta
        
        # Test today
        start, end = get_time_range('today')
        assert start < end
        assert (end - start) <= timedelta(days=1)
        
        # Test week
        start, end = get_time_range('week')
        assert (end - start) >= timedelta(days=6)
        assert (end - start) <= timedelta(days=8)
        
        # Test month
        start, end = get_time_range('month')
        assert (end - start) >= timedelta(days=29)
        assert (end - start) <= timedelta(days=31)
    
    def test_is_business_hours(self):
        """Test business hours check"""
        from api.tasks.utils import is_business_hours
        
        # Test business hours on weekday
        business_time = datetime(2023, 12, 25, 14, 0)  # 2 PM on Monday
        assert is_business_hours(business_time) is True
        
        # Test non-business hours on weekday
        non_business_time = datetime(2023, 12, 25, 20, 0)  # 8 PM on Monday
        assert is_business_hours(non_business_time) is False
        
        # Test weekend
        weekend_time = datetime(2023, 12, 23, 14, 0)  # 2 PM on Saturday
        assert is_business_hours(weekend_time) is False


class TestStringUtilities:
    """Test string utility functions"""
    
    def test_slugify(self):
        """Test string slugification"""
        from api.tasks.utils import slugify
        
        test_cases = [
            ("Hello World", "hello-world"),
            ("Python & Django", "python-django"),
            ("What's Up?", "whats-up"),
            ("Multiple   Spaces", "multiple-spaces"),
            ("---Leading and Trailing---", "leading-and-trailing"),
            ("", "")
        ]
        
        for input_str, expected in test_cases:
            result = slugify(input_str)
            assert result == expected
    
    def test_truncate_text(self):
        """Test text truncation"""
        from api.tasks.utils import truncate_text
        
        long_text = "This is a very long text that should be truncated"
        result = truncate_text(long_text, 20)
        
        assert len(result) <= 23  # 20 + "..."
        assert result.endswith("...")
    
    def test_truncate_text_short(self):
        """Test truncation with short text"""
        from api.tasks.utils import truncate_text
        
        short_text = "Short"
        result = truncate_text(short_text, 20)
        
        assert result == "Short"
    
    def test_extract_keywords(self):
        """Test keyword extraction"""
        from api.tasks.utils import extract_keywords
        
        text = "This is a test document about Python programming and web development"
        keywords = extract_keywords(text)
        
        assert isinstance(keywords, list)
        assert "python" in keywords
        assert "programming" in keywords
        assert "development" in keywords
        assert "this" not in keywords  # Should be filtered out
        assert "is" not in keywords  # Should be filtered out
    
    def test_format_currency(self):
        """Test currency formatting"""
        from api.tasks.utils import format_currency
        
        test_cases = [
            (1234.56, "USD", "$1,234.56"),
            (Decimal("99.99"), "EUR", "€99.99"),
            (500, "GBP", "£500.00"),
            (0, "USD", "$0.00")
        ]
        
        for amount, currency, expected in test_cases:
            result = format_currency(amount, currency)
            assert result == expected


class TestCacheUtilities:
    """Test cache utility functions"""
    
    @patch('tasks.utils.cache')
    def test_cache_get_success(self, mock_cache):
        """Test successful cache get"""
        from api.tasks.utils import cache_get
        
        mock_cache.get.return_value = "cached_value"
        result = cache_get("test_key")
        
        assert result == "cached_value"
        mock_cache.get.assert_called_once_with("test_key", None)
    
    @patch('tasks.utils.cache')
    def test_cache_get_default(self, mock_cache):
        """Test cache get with default"""
        from api.tasks.utils import cache_get
        
        mock_cache.get.return_value = None
        result = cache_get("test_key", "default_value")
        
        assert result == "default_value"
    
    @patch('tasks.utils.cache')
    def test_cache_set_success(self, mock_cache):
        """Test successful cache set"""
        from api.tasks.utils import cache_set
        
        result = cache_set("test_key", "test_value", 300)
        
        assert result is True
        mock_cache.set.assert_called_once_with("test_key", "test_value", 300)
    
    @patch('tasks.utils.cache')
    def test_cache_delete_success(self, mock_cache):
        """Test successful cache delete"""
        from api.tasks.utils import cache_delete
        
        result = cache_delete("test_key")
        
        assert result is True
        mock_cache.delete.assert_called_once_with("test_key")
    
    @patch('tasks.utils.cache')
    def test_cache_get_or_set_miss(self, mock_cache):
        """Test cache get or set on miss"""
        from api.tasks.utils import cache_get_or_set
        
        mock_cache.get.return_value = None
        mock_func = MagicMock(return_value="computed_value")
        
        result = cache_get_or_set("test_key", mock_func, 300)
        
        assert result == "computed_value"
        mock_cache.set.assert_called_once_with("test_key", "computed_value", 300)
    
    @patch('tasks.utils.cache')
    def test_cache_get_or_set_hit(self, mock_cache):
        """Test cache get or set on hit"""
        from api.tasks.utils import cache_get_or_set
        
        mock_cache.get.return_value = "cached_value"
        mock_func = MagicMock()
        
        result = cache_get_or_set("test_key", mock_func, 300)
        
        assert result == "cached_value"
        mock_func.assert_not_called()


class TestCalculationUtilities:
    """Test calculation utility functions"""
    
    def test_calculate_percentage(self):
        """Test percentage calculation"""
        from api.tasks.utils import calculate_percentage
        
        test_cases = [
            (25, 100, 25.0),
            (1, 3, 33.33),
            (0, 100, 0.0),
            (50, 0, 0.0),  # Division by zero
            (75, 200, 37.5)
        ]
        
        for part, total, expected in test_cases:
            result = calculate_percentage(part, total)
            assert abs(result - expected) < 0.01
    
    def test_calculate_growth_rate(self):
        """Test growth rate calculation"""
        from api.tasks.utils import calculate_growth_rate
        
        test_cases = [
            (150, 100, 50.0),
            (100, 100, 0.0),
            (50, 100, -50.0),
            (0, 0, 0.0),
            (100, 0, 100.0)  # Division by zero case
        ]
        
        for current, previous, expected in test_cases:
            result = calculate_growth_rate(current, previous)
            assert abs(result - expected) < 0.01
    
    def test_calculate_compound_interest(self):
        """Test compound interest calculation"""
        from api.tasks.utils import calculate_compound_interest
        
        principal = Decimal("1000")
        rate = Decimal("0.05")
        periods = 12
        
        result = calculate_compound_interest(principal, rate, periods)
        
        # Should be greater than principal
        assert result > principal
        # Reasonable amount for 5% monthly for 1 year
        assert result > Decimal("1500")
    
    def test_moving_average(self):
        """Test moving average calculation"""
        from api.tasks.utils import moving_average
        
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        window_size = 3
        
        result = moving_average(data, window_size)
        
        assert len(result) == len(data)
        assert result[0] == 1.0  # Average of [1]
        assert result[2] == 2.0  # Average of [1, 2, 3]
        assert result[9] == 8.0  # Average of [8, 9, 10]


class TestAPIUtilities:
    """Test API utility functions"""
    
    def test_build_api_response_success(self):
        """Test API response building for success"""
        from api.tasks.utils import build_api_response
        
        response = build_api_response(
            data={"key": "value"},
            message="Success",
            status_code=200
        )
        
        assert response['status'] == 'success'
        assert response['message'] == 'Success'
        assert response['data'] == {"key": "value"}
        assert 'timestamp' in response
    
    def test_build_api_response_error(self):
        """Test API response building for error"""
        from api.tasks.utils import build_api_response
        
        response = build_api_response(
            data=None,
            message="Error occurred",
            status_code=400
        )
        
        assert response['status'] == 'error'
        assert response['message'] == 'Error occurred'
        assert response['data'] is None
        assert 'timestamp' in response
    
    def test_validate_request_params_valid(self):
        """Test request parameter validation with valid params"""
        from api.tasks.utils import validate_request_params
        
        params = {"name": "test", "email": "test@example.com"}
        required_fields = ["name", "email"]
        
        is_valid, missing = validate_request_params(params, required_fields)
        
        assert is_valid is True
        assert missing == []
    
    def test_validate_request_params_invalid(self):
        """Test request parameter validation with missing params"""
        from api.tasks.utils import validate_request_params
        
        params = {"name": "test"}
        required_fields = ["name", "email", "password"]
        
        is_valid, missing = validate_request_params(params, required_fields)
        
        assert is_valid is False
        assert set(missing) == {"email", "password"}
    
    def test_paginate_response(self):
        """Test response pagination"""
        from api.tasks.utils import paginate_response
        
        # Mock queryset
        mock_queryset = MagicMock()
        mock_queryset.count.return_value = 100
        mock_queryset.__getitem__ = lambda self, key: list(range(20))[key[0]:key[1]]
        
        result = paginate_response(mock_queryset, page=2, page_size=20)
        
        assert 'items' in result
        assert 'pagination' in result
        assert result['pagination']['page'] == 2
        assert result['pagination']['page_size'] == 20
        assert result['pagination']['total_count'] == 100
        assert result['pagination']['total_pages'] == 5
        assert result['pagination']['has_next'] is True
        assert result['pagination']['has_previous'] is True


class TestFileUtilities:
    """Test file utility functions"""
    
    def test_generate_unique_filename(self):
        """Test unique filename generation"""
        from api.tasks.utils import generate_unique_filename
        
        filename = "document.pdf"
        result = generate_unique_filename(filename)
        
        assert result.endswith(".pdf")
        assert "document" in result
        # Should contain timestamp and random string
        assert len(result) > len(filename)
    
    def test_get_file_size_mb(self):
        """Test file size conversion to MB"""
        from api.tasks.utils import get_file_size_mb
        
        test_cases = [
            (1024 * 1024, 1.0),  # 1 MB
            (5 * 1024 * 1024, 5.0),  # 5 MB
            (0, 0.0),
            (512 * 1024, 0.5)  # 512 KB
        ]
        
        for bytes_size, expected in test_cases:
            result = get_file_size_mb(bytes_size)
            assert abs(result - expected) < 0.01
    
    def test_is_valid_image_extension(self):
        """Test image extension validation"""
        from api.tasks.utils import is_valid_image_extension
        
        valid_extensions = [
            "image.jpg", "photo.jpeg", "graphic.png", 
            "animation.gif", "picture.bmp", "webp.webp"
        ]
        
        invalid_extensions = [
            "document.pdf", "file.txt", "video.mp4", "audio.mp3"
        ]
        
        for ext in valid_extensions:
            assert is_valid_image_extension(ext) is True
        
        for ext in invalid_extensions:
            assert is_valid_image_extension(ext) is False
    
    def test_is_valid_document_extension(self):
        """Test document extension validation"""
        from api.tasks.utils import is_valid_document_extension
        
        valid_extensions = [
            "report.pdf", "document.doc", "file.docx", 
            "notes.txt", "document.rtf"
        ]
        
        invalid_extensions = [
            "image.jpg", "video.mp4", "audio.mp3", "archive.zip"
        ]
        
        for ext in valid_extensions:
            assert is_valid_document_extension(ext) is True
        
        for ext in invalid_extensions:
            assert is_valid_document_extension(ext) is False


class TestRateLimitingUtilities:
    """Test rate limiting utility functions"""
    
    @patch('tasks.utils.cache')
    def test_check_rate_limit_under_limit(self, mock_cache):
        """Test rate limit check when under limit"""
        from api.tasks.utils import check_rate_limit
        
        mock_cache.get.return_value = 5  # Current count
        mock_cache.ttl.return_value = 3000  # Remaining time
        
        is_allowed, remaining_time = check_rate_limit("test_key", limit=10)
        
        assert is_allowed is True
        mock_cache.set.assert_called_once_with("rate_limit:test_key", 6, 3600)
    
    @patch('tasks.utils.cache')
    def test_check_rate_limit_over_limit(self, mock_cache):
        """Test rate limit check when over limit"""
        from api.tasks.utils import check_rate_limit
        
        mock_cache.get.return_value = 10  # At limit
        mock_cache.ttl.return_value = 1800  # Remaining time
        
        is_allowed, remaining_time = check_rate_limit("test_key", limit=10)
        
        assert is_allowed is False
        assert remaining_time == 1800
        mock_cache.set.assert_not_called()
    
    @patch('tasks.utils.cache')
    def test_reset_rate_limit(self, mock_cache):
        """Test rate limit reset"""
        from api.tasks.utils import reset_rate_limit
        
        result = reset_rate_limit("test_key")
        
        assert result is True
        mock_cache.delete.assert_called_once_with("rate_limit:test_key")


class TestConstants:
    """Test constants class"""
    
    def test_constants_values(self):
        """Test constant values are correct"""
        from api.tasks.utils import Constants
        
        # Time periods
        assert Constants.SECOND == 1
        assert Constants.MINUTE == 60
        assert Constants.HOUR == 3600
        assert Constants.DAY == 86400
        
        # File sizes
        assert Constants.MAX_IMAGE_SIZE == 5 * 1024 * 1024
        assert Constants.MAX_DOCUMENT_SIZE == 10 * 1024 * 1024
        
        # Pagination
        assert Constants.DEFAULT_PAGE_SIZE == 20
        assert Constants.MAX_PAGE_SIZE == 100
        
        # Rate limits
        assert Constants.DEFAULT_RATE_LIMIT == 100
        assert Constants.AUTHENTICATED_RATE_LIMIT == 1000
