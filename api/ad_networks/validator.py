"""
api/ad_networks/validator.py
Validation utilities for ad networks module
SaaS-ready with tenant support
"""

import re
import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urlparse
import requests

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from django.core.validators import URLValidator, EmailValidator

logger = logging.getLogger(__name__)


class AdNetworkValidator:
    """Validator for AdNetwork model"""
    
    @staticmethod
    def validate_api_key(api_key: str, network_type: str = None) -> bool:
        """Validate API key format"""
        if not api_key:
            return False
        
        # Basic length check
        if len(api_key) < 10:
            return False
        
        # Network-specific validation
        if network_type:
            return AdNetworkValidator._validate_api_key_by_type(api_key, network_type)
        
        # Generic validation
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', api_key))
    
    @staticmethod
    def _validate_api_key_by_type(api_key: str, network_type: str) -> bool:
        """Validate API key by network type"""
        patterns = {
            'adscend': r'^[a-zA-Z0-9]{32,}$',
            'offertoro': r'^[a-zA-Z0-9]{20,}$',
            'adgem': r'^[a-zA-Z0-9]{24,}$',
            'ayetstudios': r'^[a-zA-Z0-9]{16,}$',
            'pollfish': r'^[a-zA-Z0-9]{40,}$',
            'cpxresearch': r'^[a-zA-Z0-9]{32,}$',
            'bitlabs': r'^[a-zA-Z0-9]{28,}$',
            'inbrain': r'^[a-zA-Z0-9]{36,}$',
            'theoremreach': r'^[a-zA-Z0-9]{30,}$',
            'yoursurveys': r'^[a-zA-Z0-9]{25,}$',
            'toluna': r'^[a-zA-Z0-9]{20,}$',
            'swagbucks': r'^[a-zA-Z0-9]{15,}$',
            'prizerebel': r'^[a-zA-Z0-9]{18,}$'
        }
        
        pattern = patterns.get(network_type.lower())
        if pattern:
            return bool(re.match(pattern, api_key))
        
        return True
    
    @staticmethod
    def validate_base_url(url: str) -> bool:
        """Validate base URL"""
        if not url:
            return False
        
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except:
            return False
    
    @staticmethod
    def validate_postback_url(url: str) -> bool:
        """Validate postback URL"""
        if not url:
            return True  # Optional field
        
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except:
            return False
    
    @staticmethod
    def validate_commission_rate(rate: Union[int, float, str]) -> bool:
        """Validate commission rate"""
        try:
            rate_value = float(rate)
            return 0 <= rate_value <= 100
        except:
            return False
    
    @staticmethod
    def validate_rating(rating: Union[int, float, str]) -> bool:
        """Validate rating"""
        try:
            rating_value = float(rating)
            return 0 <= rating_value <= 5
        except:
            return False
    
    @staticmethod
    def validate_trust_score(score: Union[int, float, str]) -> bool:
        """Validate trust score"""
        try:
            score_value = float(score)
            return 0 <= score_value <= 100
        except:
            return False


class OfferValidator:
    """Validator for Offer model"""
    
    @staticmethod
    def validate_title(title: str) -> bool:
        """Validate offer title"""
        if not title:
            return False
        
        # Length check
        if len(title) < 3 or len(title) > 200:
            return False
        
        # Character check
        return bool(re.match(r'^[a-zA-Z0-9\s\-_.,!?&()]+$', title))
    
    @staticmethod
    def validate_description(description: str) -> bool:
        """Validate offer description"""
        if not description:
            return True  # Optional field
        
        # Length check
        if len(description) > 2000:
            return False
        
        return True
    
    @staticmethod
    def validate_reward_amount(amount: Union[int, float, str, Decimal], 
                            currency: str = 'USD') -> bool:
        """Validate reward amount"""
        try:
            amount_value = Decimal(str(amount))
            
            # Positive amount
            if amount_value <= 0:
                return False
            
            # Maximum amount
            if amount_value > Decimal('10000'):
                return False
            
            # Currency-specific validation
            return OfferValidator._validate_amount_by_currency(amount_value, currency)
            
        except (InvalidOperation, ValueError):
            return False
    
    @staticmethod
    def _validate_amount_by_currency(amount: Decimal, currency: str) -> bool:
        """Validate amount by currency"""
        # Decimal places check
        if currency.upper() in ['USD', 'EUR', 'GBP']:
            # 2 decimal places for major currencies
            return amount.as_tuple().exponent >= -2
        elif currency.upper() in ['JPY', 'KRW']:
            # No decimal places for these currencies
            return amount.as_tuple().exponent >= 0
        else:
            # Allow up to 4 decimal places for other currencies
            return amount.as_tuple().exponent >= -4
    
    @staticmethod
    def validate_countries(countries: List[str]) -> bool:
        """Validate countries list"""
        if not countries:
            return True  # Optional field
        
        # Valid country codes
        valid_countries = [
            'US', 'GB', 'CA', 'AU', 'DE', 'FR', 'IT', 'ES', 'NL', 'SE',
            'NO', 'DK', 'FI', 'AT', 'CH', 'BE', 'IE', 'PT', 'GR', 'PL',
            'CZ', 'HU', 'RO', 'BG', 'HR', 'SI', 'SK', 'EE', 'LV', 'LT',
            'RU', 'UA', 'BY', 'KZ', 'UZ', 'KG', 'TJ', 'TM', 'GE', 'AM',
            'AZ', 'TR', 'CY', 'IL', 'JO', 'SY', 'LB', 'IQ', 'IR', 'AF',
            'PK', 'IN', 'BD', 'LK', 'NP', 'BT', 'MM', 'TH', 'VN', 'KH',
            'LA', 'MY', 'SG', 'ID', 'PH', 'BN', 'TL', 'PG', 'AU', 'NZ',
            'FJ', 'SB', 'VU', 'NC', 'PF', 'CK', 'TO', 'WS', 'KI', 'TV',
            'NU', 'PW', 'MH', 'FM', 'MP', 'GU', 'VI', 'PR', 'DO', 'HT',
            'JM', 'BB', 'TT', 'GD', 'LC', 'VC', 'AG', 'DM', 'KN', 'AN',
            'AW', 'CW', 'SX', 'BQ', 'PA', 'CR', 'NI', 'SV', 'GT', 'HN',
            'BZ', 'MX', 'CU', 'JM', 'HT', 'DO', 'PR', 'US', 'CA', 'GL',
            'BR', 'AR', 'CL', 'BO', 'PE', 'EC', 'CO', 'VE', 'GY', 'SR',
            'GF', 'PY', 'UY', 'ZA', 'NA', 'BW', 'ZW', 'MZ', 'MW', 'ZM',
            'AO', 'CD', 'CG', 'GA', 'GQ', 'ST', 'CM', 'CF', 'TD', 'NE',
            'ML', 'BF', 'SN', 'CI', 'LR', 'GH', 'TG', 'BJ', 'NG', 'TD',
            'ER', 'ET', 'SO', 'KE', 'UG', 'RW', 'BI', 'TZ', 'MW', 'ZM',
            'MW', 'AO', 'NA', 'BW', 'ZW', 'MZ', 'SZ', 'LS'
        ]
        
        return all(country.upper() in valid_countries for country in countries)
    
    @staticmethod
    def validate_platforms(platforms: List[str]) -> bool:
        """Validate platforms list"""
        if not platforms:
            return True  # Optional field
        
        valid_platforms = ['android', 'ios', 'web', 'desktop', 'mobile', 'tablet']
        
        return all(platform.lower() in valid_platforms for platform in platforms)
    
    @staticmethod
    def validate_device_type(device_type: str) -> bool:
        """Validate device type"""
        valid_types = ['mobile', 'desktop', 'tablet', 'any']
        return device_type.lower() in valid_types
    
    @staticmethod
    def validate_difficulty(difficulty: str) -> bool:
        """Validate difficulty level"""
        valid_levels = ['easy', 'medium', 'hard', 'expert']
        return difficulty.lower() in valid_levels
    
    @staticmethod
    def validate_estimated_time(time_minutes: Union[int, str]) -> bool:
        """Validate estimated time"""
        try:
            time_value = int(time_minutes)
            return 1 <= time_value <= 1440  # 1 minute to 24 hours
        except:
            return False
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL"""
        if not url:
            return True  # Optional field
        
        try:
            validator = URLValidator()
            validator(url)
            return True
        except:
            return False
    
    @staticmethod
    def validate_expires_at(expires_at: datetime) -> bool:
        """Validate expiration date"""
        if not expires_at:
            return True  # Optional field
        
        return expires_at > timezone.now()


class ConversionValidator:
    """Validator for Conversion model"""
    
    @staticmethod
    def validate_payout(payout: Union[int, float, str, Decimal], 
                       currency: str = 'USD') -> bool:
        """Validate payout amount"""
        # Use same validation as offer reward amount
        return OfferValidator.validate_reward_amount(payout, currency)
    
    @staticmethod
    def validate_fraud_score(score: Union[int, float, str]) -> bool:
        """Validate fraud score"""
        try:
            score_value = float(score)
            return 0 <= score_value <= 100
        except:
            return False
    
    @staticmethod
    def validate_conversion_status(status: str) -> bool:
        """Validate conversion status"""
        valid_statuses = ['pending', 'approved', 'rejected', 'chargeback']
        return status.lower() in valid_statuses
    
    @staticmethod
    def validate_conversion_data(data: Dict[str, Any]) -> bool:
        """Validate conversion data"""
        if not isinstance(data, dict):
            return False
        
        # Check for required fields
        required_fields = ['conversion_id', 'user_id', 'offer_id', 'payout']
        return all(field in data for field in required_fields)


class RewardValidator:
    """Validator for Reward model"""
    
    @staticmethod
    def validate_amount(amount: Union[int, float, str, Decimal], 
                      currency: str = 'USD') -> bool:
        """Validate reward amount"""
        return OfferValidator.validate_reward_amount(amount, currency)
    
    @staticmethod
    def validate_currency(currency: str) -> bool:
        """Validate currency code"""
        if not currency:
            return False
        
        valid_currencies = [
            'USD', 'EUR', 'GBP', 'JPY', 'KRW', 'CNY', 'INR', 'BRL', 'MXN',
            'CAD', 'AUD', 'CHF', 'SEK', 'NOK', 'DKK', 'PLN', 'CZK', 'HUF',
            'RUB', 'TRY', 'ZAR', 'NGN', 'KES', 'GHS', 'EGP', 'SAR', 'AED'
        ]
        
        return currency.upper() in valid_currencies
    
    @staticmethod
    def validate_status(status: str) -> bool:
        """Validate reward status"""
        valid_statuses = ['pending', 'approved', 'paid', 'cancelled']
        return status.lower() in valid_statuses
    
    @staticmethod
    def validate_payment_method(method: str) -> bool:
        """Validate payment method"""
        valid_methods = ['paypal', 'bank_transfer', 'crypto', 'gift_card', 'check']
        return method.lower() in valid_methods


class UserValidator:
    """Validator for User-related data"""
    
    @staticmethod
    def validate_ip_address(ip: str) -> bool:
        """Validate IP address"""
        if not ip:
            return False
        
        # IPv4 pattern
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        
        # IPv6 pattern (simplified)
        ipv6_pattern = r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
        
        return bool(re.match(ipv4_pattern, ip) or re.match(ipv6_pattern, ip))
    
    @staticmethod
    def validate_user_agent(user_agent: str) -> bool:
        """Validate user agent string"""
        if not user_agent:
            return False
        
        # Basic length check
        if len(user_agent) < 10 or len(user_agent) > 500:
            return False
        
        return True
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email address"""
        if not email:
            return False
        
        try:
            validator = EmailValidator()
            validator(email)
            return True
        except:
            return False
    
    @staticmethod
    def validate_country(country: str) -> bool:
        """Validate country code"""
        if not country:
            return False
        
        return OfferValidator.validate_countries([country])


class SecurityValidator:
    """Security-related validators"""
    
    @staticmethod
    def validate_sql_injection(input_string: str) -> bool:
        """Check for SQL injection patterns"""
        if not input_string:
            return True
        
        # Common SQL injection patterns
        sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
            r"(--|#|\/\*|\*\/)",
            r"(\bOR\b.*=.*\bOR\b)",
            r"(\bAND\b.*=.*\bAND\b)",
            r"(\bWHERE\b.*\bOR\b)",
            r"(\bWHERE\b.*\bAND\b)",
            r"(\bHAVING\b.*\bOR\b)",
            r"(\bHAVING\b.*\bAND\b)",
            r"(\bGROUP BY\b.*\bORDER BY\b)",
            r"(\bORDER BY\b.*\bLIMIT\b)",
            r"(\bLIMIT\b.*\bOFFSET\b)"
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, input_string, re.IGNORECASE):
                return False
        
        return True
    
    @staticmethod
    def validate_xss(input_string: str) -> bool:
        """Check for XSS patterns"""
        if not input_string:
            return True
        
        # Common XSS patterns
        xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"<iframe[^>]*>.*?</iframe>",
            r"<object[^>]*>.*?</object>",
            r"<embed[^>]*>.*?</embed>",
            r"<link[^>]*>",
            r"<meta[^>]*>",
            r"javascript:",
            r"vbscript:",
            r"onload=",
            r"onerror=",
            r"onclick=",
            r"onmouseover=",
            r"onfocus=",
            r"onblur=",
            r"onchange=",
            r"onsubmit="
        ]
        
        for pattern in xss_patterns:
            if re.search(pattern, input_string, re.IGNORECASE):
                return False
        
        return True
    
    @staticmethod
    def validate_file_upload(filename: str, content_type: str, 
                          file_size: int) -> Dict[str, Any]:
        """Validate file upload"""
        result = {
            'valid': True,
            'errors': []
        }
        
        # Filename validation
        if not filename:
            result['valid'] = False
            result['errors'].append('Filename is required')
        else:
            # Check for dangerous extensions
            dangerous_extensions = ['.exe', '.bat', '.cmd', '.scr', '.pif', '.com', '.vbs', '.js', '.jar']
            file_ext = filename.lower().split('.')[-1]
            
            if any(filename.lower().endswith(ext) for ext in dangerous_extensions):
                result['valid'] = False
                result['errors'].append('Dangerous file type')
        
        # Content type validation
        allowed_types = [
            'image/jpeg', 'image/png', 'image/gif', 'image/webp',
            'text/csv', 'application/csv',
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ]
        
        if content_type not in allowed_types:
            result['valid'] = False
            result['errors'].append('Invalid content type')
        
        # File size validation (10MB max)
        max_size = 10 * 1024 * 1024
        if file_size > max_size:
            result['valid'] = False
            result['errors'].append('File too large')
        
        return result


class DataValidator:
    """General data validation utilities"""
    
    @staticmethod
    def validate_required_fields(data: Dict[str, Any], 
                             required_fields: List[str]) -> Dict[str, Any]:
        """Validate required fields"""
        result = {
            'valid': True,
            'missing_fields': []
        }
        
        for field in required_fields:
            if field not in data or data[field] is None or data[field] == '':
                result['valid'] = False
                result['missing_fields'].append(field)
        
        return result
    
    @staticmethod
    def validate_field_types(data: Dict[str, Any], 
                          field_types: Dict[str, type]) -> Dict[str, Any]:
        """Validate field types"""
        result = {
            'valid': True,
            'type_errors': []
        }
        
        for field, expected_type in field_types.items():
            if field in data and data[field] is not None:
                if not isinstance(data[field], expected_type):
                    result['valid'] = False
                    result['type_errors'].append(f'{field} should be {expected_type.__name__}')
        
        return result
    
    @staticmethod
    def validate_string_length(data: Dict[str, Any], 
                            length_rules: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
        """Validate string lengths"""
        result = {
            'valid': True,
            'length_errors': []
        }
        
        for field, rules in length_rules.items():
            if field in data and isinstance(data[field], str):
                value = data[field]
                min_length = rules.get('min', 0)
                max_length = rules.get('max', float('inf'))
                
                if len(value) < min_length or len(value) > max_length:
                    result['valid'] = False
                    result['length_errors'].append(
                        f'{field} length must be between {min_length} and {max_length}'
                    )
        
        return result
    
    @staticmethod
    def validate_numeric_ranges(data: Dict[str, Any], 
                            range_rules: Dict[str, Dict[str, Union[int, float]]]) -> Dict[str, Any]:
        """Validate numeric ranges"""
        result = {
            'valid': True,
            'range_errors': []
        }
        
        for field, rules in range_rules.items():
            if field in data:
                try:
                    value = float(data[field])
                    min_value = rules.get('min', float('-inf'))
                    max_value = rules.get('max', float('inf'))
                    
                    if value < min_value or value > max_value:
                        result['valid'] = False
                        result['range_errors'].append(
                            f'{field} must be between {min_value} and {max_value}'
                        )
                except (ValueError, TypeError):
                    result['valid'] = False
                    result['range_errors'].append(f'{field} must be a number')
        
        return result


# Validation helper functions
def validate_offer_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate complete offer data"""
    validator = OfferValidator()
    security_validator = SecurityValidator()
    data_validator = DataValidator()
    
    result = {
        'valid': True,
        'errors': []
    }
    
    # Required fields
    required_fields = ['title', 'reward_amount']
    required_result = data_validator.validate_required_fields(data, required_fields)
    
    if not required_result['valid']:
        result['valid'] = False
        result['errors'].extend([f"Missing: {field}" for field in required_result['missing_fields']])
    
    # Field validation
    if 'title' in data:
        if not validator.validate_title(data['title']):
            result['valid'] = False
            result['errors'].append('Invalid title')
        
        if not security_validator.validate_xss(data['title']):
            result['valid'] = False
            result['errors'].append('Title contains potentially dangerous content')
    
    if 'description' in data and data['description']:
        if not validator.validate_description(data['description']):
            result['valid'] = False
            result['errors'].append('Invalid description')
        
        if not security_validator.validate_xss(data['description']):
            result['valid'] = False
            result['errors'].append('Description contains potentially dangerous content')
    
    if 'reward_amount' in data:
        if not validator.validate_reward_amount(data['reward_amount']):
            result['valid'] = False
            result['errors'].append('Invalid reward amount')
    
    if 'countries' in data and data['countries']:
        if not validator.validate_countries(data['countries']):
            result['valid'] = False
            result['errors'].append('Invalid countries list')
    
    if 'platforms' in data and data['platforms']:
        if not validator.validate_platforms(data['platforms']):
            result['valid'] = False
            result['errors'].append('Invalid platforms list')
    
    if 'device_type' in data and data['device_type']:
        if not validator.validate_device_type(data['device_type']):
            result['valid'] = False
            result['errors'].append('Invalid device type')
    
    if 'difficulty' in data and data['difficulty']:
        if not validator.validate_difficulty(data['difficulty']):
            result['valid'] = False
            result['errors'].append('Invalid difficulty level')
    
    if 'estimated_time' in data and data['estimated_time']:
        if not validator.validate_estimated_time(data['estimated_time']):
            result['valid'] = False
            result['errors'].append('Invalid estimated time')
    
    if 'preview_url' in data and data['preview_url']:
        if not validator.validate_url(data['preview_url']):
            result['valid'] = False
            result['errors'].append('Invalid preview URL')
    
    if 'tracking_url' in data and data['tracking_url']:
        if not validator.validate_url(data['tracking_url']):
            result['valid'] = False
            result['errors'].append('Invalid tracking URL')
    
    if 'expires_at' in data and data['expires_at']:
        if not validator.validate_expires_at(data['expires_at']):
            result['valid'] = False
            result['errors'].append('Invalid expiration date')
    
    return result


def validate_conversion_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate complete conversion data"""
    validator = ConversionValidator()
    data_validator = DataValidator()
    
    result = {
        'valid': True,
        'errors': []
    }
    
    # Required fields
    required_fields = ['conversion_id', 'user_id', 'offer_id', 'payout']
    required_result = data_validator.validate_required_fields(data, required_fields)
    
    if not required_result['valid']:
        result['valid'] = False
        result['errors'].extend([f"Missing: {field}" for field in required_result['missing_fields']])
    
    # Field validation
    if 'payout' in data:
        if not validator.validate_payout(data['payout']):
            result['valid'] = False
            result['errors'].append('Invalid payout amount')
    
    if 'fraud_score' in data:
        if not validator.validate_fraud_score(data['fraud_score']):
            result['valid'] = False
            result['errors'].append('Invalid fraud score')
    
    if 'conversion_status' in data:
        if not validator.validate_conversion_status(data['conversion_status']):
            result['valid'] = False
            result['errors'].append('Invalid conversion status')
    
    if 'conversion_data' in data:
        if not validator.validate_conversion_data(data['conversion_data']):
            result['valid'] = False
            result['errors'].append('Invalid conversion data')
    
    return result


def validate_reward_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate complete reward data"""
    validator = RewardValidator()
    data_validator = DataValidator()
    
    result = {
        'valid': True,
        'errors': []
    }
    
    # Required fields
    required_fields = ['amount', 'currency']
    required_result = data_validator.validate_required_fields(data, required_fields)
    
    if not required_result['valid']:
        result['valid'] = False
        result['errors'].extend([f"Missing: {field}" for field in required_result['missing_fields']])
    
    # Field validation
    if 'amount' in data:
        if not validator.validate_amount(data['amount']):
            result['valid'] = False
            result['errors'].append('Invalid amount')
    
    if 'currency' in data:
        if not validator.validate_currency(data['currency']):
            result['valid'] = False
            result['errors'].append('Invalid currency')
    
    if 'status' in data:
        if not validator.validate_status(data['status']):
            result['valid'] = False
            result['errors'].append('Invalid status')
    
    if 'payment_method' in data:
        if not validator.validate_payment_method(data['payment_method']):
            result['valid'] = False
            result['errors'].append('Invalid payment method')
    
    return result


# Export all validators
__all__ = [
    # Validator classes
    'AdNetworkValidator',
    'OfferValidator',
    'ConversionValidator',
    'RewardValidator',
    'UserValidator',
    'SecurityValidator',
    'DataValidator',
    
    # Validation functions
    'validate_offer_data',
    'validate_conversion_data',
    'validate_reward_data'
]
