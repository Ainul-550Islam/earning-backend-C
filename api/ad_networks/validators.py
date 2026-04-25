"""
api/ad_networks/validators.py
Custom validators for ad networks module
SaaS-ready with tenant support
"""

import re
import json
import hashlib
import hmac
import requests
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse
from datetime import datetime, timedelta
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, RegexValidator
from django.utils import timezone
from django.conf import settings
import logging

from api.ad_networks.models import AdNetwork, Offer, UserOfferEngagement
from api.ad_networks.choices import NetworkType, PaymentMethod
from api.ad_networks.constants import (
    MIN_PAYOUT_AMOUNT,
    MAX_PAYOUT_AMOUNT,
    MAX_OFFER_TITLE_LENGTH,
    MAX_OFFER_URL_LENGTH,
    FRAUD_SCORE_THRESHOLD,
    SUPPORTED_CURRENCIES
)

logger = logging.getLogger(__name__)


# ==================== PAYOUT VALIDATORS ====================

def validate_payout_amount(amount, currency='USD'):
    """
    Validate payout amount with currency-specific rules
    """
    try:
        # Convert to Decimal
        if isinstance(amount, str):
            amount = Decimal(str(amount).replace(',', ''))
        elif isinstance(amount, (int, float)):
            amount = Decimal(str(amount))
        elif not isinstance(amount, Decimal):
            raise ValidationError("Amount must be a valid number")
        
        # Check if amount is positive
        if amount <= 0:
            raise ValidationError("Payout amount must be positive")
        
        # Currency-specific validation
        if currency.upper() == 'BDT':
            # BDT typically has smaller minimum amounts
            min_amount = Decimal('1.00')
            max_amount = Decimal('50000.00')
        elif currency.upper() == 'INR':
            min_amount = Decimal('10.00')
            max_amount = Decimal('100000.00')
        else:
            min_amount = MIN_PAYOUT_AMOUNT
            max_amount = MAX_PAYOUT_AMOUNT
        
        # Check range
        if amount < min_amount:
            raise ValidationError(f"Minimum payout amount is {min_amount} {currency}")
        
        if amount > max_amount:
            raise ValidationError(f"Maximum payout amount is {max_amount} {currency}")
        
        # Check decimal places (max 2 for most currencies)
        if amount.as_tuple().exponent < -2:
            raise ValidationError("Amount cannot have more than 2 decimal places")
        
        return amount
        
    except (InvalidOperation, ValueError) as e:
        raise ValidationError(f"Invalid payout amount: {str(e)}")


def validate_commission_rate(rate):
    """
    Validate commission rate (0-100%)
    """
    try:
        if isinstance(rate, str):
            rate = float(rate.replace('%', ''))
        elif not isinstance(rate, (int, float)):
            raise ValidationError("Commission rate must be a number")
        
        if rate < 0:
            raise ValidationError("Commission rate cannot be negative")
        
        if rate > 100:
            raise ValidationError("Commission rate cannot exceed 100%")
        
        # Check for reasonable commission rates
        if rate > 50:
            logger.warning(f"High commission rate detected: {rate}%")
        
        return float(rate)
        
    except (ValueError, TypeError) as e:
        raise ValidationError(f"Invalid commission rate: {str(e)}")


def validate_payout_currency(currency):
    """
    Validate payout currency code
    """
    if not currency or not isinstance(currency, str):
        raise ValidationError("Currency is required")
    
    currency = currency.upper().strip()
    
    if currency not in SUPPORTED_CURRENCIES:
        raise ValidationError(f"Currency '{currency}' is not supported")
    
    return currency


# ==================== OFFER URL VALIDATORS ====================

def validate_offer_url(url, check_ssl=True):
    """
    Validate offer URL with security checks
    """
    if not url:
        raise ValidationError("URL is required")
    
    # Basic URL validation
    url_validator = URLValidator()
    try:
        url_validator(url)
    except ValidationError:
        raise ValidationError("Invalid URL format")
    
    # Parse URL
    parsed = urlparse(url)
    
    # Check scheme
    if parsed.scheme not in ['http', 'https']:
        raise ValidationError("URL must use HTTP or HTTPS protocol")
    
    # Check SSL requirement
    if check_ssl and parsed.scheme != 'https':
        logger.warning(f"Non-HTTPS URL detected: {url}")
        # For production, you might want to enforce HTTPS
        # raise ValidationError("URL must use HTTPS protocol")
    
    # Check domain validity
    if not parsed.netloc:
        raise ValidationError("URL must have a valid domain")
    
    # Check for suspicious patterns
    suspicious_patterns = [
        r'bit\.ly',
        r'tinyurl\.com',
        r'short\.link',
        r'goo\.gl',
        r't\.cn',  # Chinese domains (often suspicious)
        r'\.tk',   # Free domains (often suspicious)
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, parsed.netloc, re.IGNORECASE):
            logger.warning(f"Suspicious URL pattern detected: {url}")
    
    # Check URL length
    if len(url) > MAX_OFFER_URL_LENGTH:
        raise ValidationError(f"URL cannot exceed {MAX_OFFER_URL_LENGTH} characters")
    
    # Check for URL parameters that might indicate fraud
    if parsed.query:
        suspicious_params = [
            'sub_id', 'aff_id', 'click_id', 'transaction_id',
            'user_id', 'session_id', 'token', 'key'
        ]
        
        for param in suspicious_params:
            if param in parsed.query:
                logger.info(f"URL contains tracking parameter: {param}")
    
    return url


def validate_network_url(url, network_type=None):
    """
    Validate network-specific URL with known patterns
    """
    if not url:
        raise ValidationError("Network URL is required")
    
    # Basic validation
    validate_offer_url(url, check_ssl=False)
    
    parsed = urlparse(url)
    
    # Network-specific validation
    if network_type:
        known_domains = {
            'adscend': ['adscendmedia.com'],
            'offertoro': ['offertoro.com'],
            'adgem': ['adgem.com'],
            'ayetstudios': ['ayetstudios.com'],
            'pollfish': ['pollfish.com'],
            'cpxresearch': ['cpx-research.com'],
        }
        
        if network_type in known_domains:
            expected_domains = known_domains[network_type]
            domain_match = any(
                domain in parsed.netloc.lower() 
                for domain in expected_domains
            )
            
            if not domain_match:
                logger.warning(f"URL domain doesn't match expected for {network_type}: {parsed.netloc}")
    
    return url


def validate_postback_url(url):
    """
    Validate postback URL format
    """
    if not url:
        raise ValidationError("Postback URL is required")
    
    # Basic URL validation
    validate_offer_url(url, check_ssl=True)
    
    # Check for required postback parameters
    required_params = ['{user_id}', '{offer_id}', '{conversion_id}', '{payout}']
    parsed = urlparse(url)
    
    missing_params = []
    for param in required_params:
        if param not in url:
            missing_params.append(param)
    
    if missing_params:
        raise ValidationError(
            f"Postback URL must contain parameters: {', '.join(missing_params)}"
        )
    
    return url


# ==================== NETWORK API KEY VALIDATORS ====================

def validate_network_api_key(api_key, network_type=None):
    """
    Validate network API key format and existence
    """
    if not api_key:
        raise ValidationError("API key is required")
    
    if not isinstance(api_key, str):
        raise ValidationError("API key must be a string")
    
    # Length validation
    if len(api_key) < 10:
        raise ValidationError("API key is too short")
    
    if len(api_key) > 500:
        raise ValidationError("API key is too long")
    
    # Format validation (basic checks)
    if api_key.startswith(' ') or api_key.endswith(' '):
        raise ValidationError("API key cannot start or end with spaces")
    
    # Network-specific format validation
    if network_type:
        format_patterns = {
            'adscend': r'^[a-f0-9]{32}$',  # MD5-like
            'offertoro': r'^[a-zA-Z0-9]{20,40}$',
            'adgem': r'^[a-zA-Z0-9]{32}$',
            'pollfish': r'^[a-zA-Z0-9_-]{20,50}$',
        }
        
        if network_type in format_patterns:
            pattern = format_patterns[network_type]
            if not re.match(pattern, api_key):
                logger.warning(f"API key format doesn't match expected for {network_type}")
    
    # Check for common weak patterns
    weak_patterns = [
        r'123456',
        r'password',
        r'test',
        r'demo',
        r'sample',
        r'admin',
    ]
    
    for pattern in weak_patterns:
        if re.search(pattern, api_key, re.IGNORECASE):
            raise ValidationError("API key contains weak pattern")
    
    return api_key


def validate_api_credentials(api_key, api_secret=None, network_type=None):
    """
    Validate API credentials pair
    """
    # Validate API key
    validate_network_api_key(api_key, network_type)
    
    # Validate API secret if provided
    if api_secret:
        if not isinstance(api_secret, str):
            raise ValidationError("API secret must be a string")
        
        if len(api_secret) < 10:
            raise ValidationError("API secret is too short")
        
        # Check if key and secret are the same (weak)
        if api_key == api_secret:
            raise ValidationError("API key and secret cannot be the same")
    
    return True


def test_network_api_connection(network_type, api_key, api_secret=None, timeout=30):
    """
    Test network API connection with provided credentials
    """
    try:
        # Get network API endpoints
        api_endpoints = {
            'adscend': 'https://api.adscendmedia.com/v1/ping',
            'offertoro': 'https://api.offertoro.com/v1/ping',
            'adgem': 'https://api.adgem.com/v1/ping',
            'pollfish': 'https://api.pollfish.com/v1/ping',
        }
        
        if network_type not in api_endpoints:
            logger.warning(f"No test endpoint for network type: {network_type}")
            return True  # Assume valid if no test endpoint
        
        endpoint = api_endpoints[network_type]
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'AdNetworks-API-Test/1.0'
        }
        
        # Add authentication
        if api_secret:
            headers['Authorization'] = f'Bearer {api_key}'
        else:
            headers['X-API-Key'] = api_key
        
        # Make test request
        response = requests.get(
            endpoint,
            headers=headers,
            timeout=timeout
        )
        
        # Check response
        if response.status_code == 200:
            return True
        elif response.status_code == 401:
            raise ValidationError("Invalid API credentials")
        elif response.status_code == 403:
            raise ValidationError("API access forbidden")
        elif response.status_code == 404:
            logger.warning(f"API endpoint not found: {endpoint}")
            return True  # Assume valid if endpoint doesn't exist
        else:
            logger.warning(f"API test failed with status {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        raise ValidationError("API connection timeout")
    except requests.exceptions.ConnectionError:
        raise ValidationError("Cannot connect to API")
    except Exception as e:
        logger.error(f"API test error: {str(e)}")
        raise ValidationError(f"API test failed: {str(e)}")


# ==================== CONVERSION DATA VALIDATORS ====================

def validate_conversion_data(conversion_data):
    """
    Validate conversion data structure and content
    """
    if not conversion_data:
        raise ValidationError("Conversion data is required")
    
    if isinstance(conversion_data, str):
        try:
            conversion_data = json.loads(conversion_data)
        except json.JSONDecodeError:
            raise ValidationError("Invalid JSON format in conversion data")
    
    if not isinstance(conversion_data, dict):
        raise ValidationError("Conversion data must be a JSON object")
    
    # Required fields validation
    required_fields = ['user_id', 'offer_id', 'payout', 'status']
    missing_fields = []
    
    for field in required_fields:
        if field not in conversion_data:
            missing_fields.append(field)
    
    if missing_fields:
        raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")
    
    # Validate specific fields
    validate_conversion_user_id(conversion_data.get('user_id'))
    validate_conversion_offer_id(conversion_data.get('offer_id'))
    validate_conversion_payout(conversion_data.get('payout'))
    validate_conversion_status(conversion_data.get('status'))
    
    # Optional fields validation
    if 'conversion_id' in conversion_data:
        validate_conversion_id(conversion_data.get('conversion_id'))
    
    if 'currency' in conversion_data:
        validate_payout_currency(conversion_data.get('currency'))
    
    if 'timestamp' in conversion_data:
        validate_conversion_timestamp(conversion_data.get('timestamp'))
    
    return conversion_data


def validate_conversion_user_id(user_id):
    """
    Validate conversion user ID
    """
    if not user_id:
        raise ValidationError("User ID is required")
    
    if isinstance(user_id, str):
        if not user_id.strip():
            raise ValidationError("User ID cannot be empty")
        # Check for suspicious patterns
        if re.match(r'^[0-9]+$', user_id):
            logger.warning(f"Numeric user ID detected: {user_id}")
    elif isinstance(user_id, int):
        if user_id <= 0:
            raise ValidationError("User ID must be positive")
    else:
        raise ValidationError("User ID must be a string or integer")
    
    return user_id


def validate_conversion_offer_id(offer_id):
    """
    Validate conversion offer ID
    """
    if not offer_id:
        raise ValidationError("Offer ID is required")
    
    if isinstance(offer_id, str):
        if not offer_id.strip():
            raise ValidationError("Offer ID cannot be empty")
    elif isinstance(offer_id, int):
        if offer_id <= 0:
            raise ValidationError("Offer ID must be positive")
    else:
        raise ValidationError("Offer ID must be a string or integer")
    
    return offer_id


def validate_conversion_payout(payout, currency='USD'):
    """
    Validate conversion payout amount
    """
    try:
        # Use existing payout validator
        amount = validate_payout_amount(payout, currency)
        
        # Additional conversion-specific checks
        if amount < Decimal('0.01'):
            raise ValidationError("Conversion payout must be at least 0.01")
        
        # Check for unusually high payouts (potential fraud)
        if currency.upper() == 'USD' and amount > Decimal('1000.00'):
            logger.warning(f"High conversion payout detected: {amount} {currency}")
        
        return amount
        
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"Invalid payout amount: {str(e)}")


def validate_conversion_status(status):
    """
    Validate conversion status
    """
    valid_statuses = ['pending', 'approved', 'rejected', 'chargeback', 'disputed']
    
    if not status:
        raise ValidationError("Conversion status is required")
    
    if not isinstance(status, str):
        raise ValidationError("Conversion status must be a string")
    
    status = status.lower().strip()
    
    if status not in valid_statuses:
        raise ValidationError(f"Invalid conversion status. Must be one of: {', '.join(valid_statuses)}")
    
    return status


def validate_conversion_id(conversion_id):
    """
    Validate conversion ID format
    """
    if not conversion_id:
        raise ValidationError("Conversion ID is required")
    
    if not isinstance(conversion_id, str):
        raise ValidationError("Conversion ID must be a string")
    
    conversion_id = conversion_id.strip()
    
    if not conversion_id:
        raise ValidationError("Conversion ID cannot be empty")
    
    # Check format (alphanumeric with some special chars)
    if not re.match(r'^[a-zA-Z0-9_-]+$', conversion_id):
        raise ValidationError("Conversion ID contains invalid characters")
    
    # Check length
    if len(conversion_id) < 3:
        raise ValidationError("Conversion ID is too short")
    
    if len(conversion_id) > 100:
        raise ValidationError("Conversion ID is too long")
    
    return conversion_id


def validate_conversion_timestamp(timestamp):
    """
    Validate conversion timestamp
    """
    if not timestamp:
        raise ValidationError("Conversion timestamp is required")
    
    # Parse timestamp
    if isinstance(timestamp, str):
        try:
            # Try ISO format first
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            try:
                # Try Unix timestamp
                timestamp = datetime.fromtimestamp(float(timestamp))
            except (ValueError, OSError):
                raise ValidationError("Invalid timestamp format")
    elif isinstance(timestamp, (int, float)):
        try:
            timestamp = datetime.fromtimestamp(timestamp)
        except (ValueError, OSError):
            raise ValidationError("Invalid timestamp value")
    elif not isinstance(timestamp, datetime):
        raise ValidationError("Timestamp must be a datetime object")
    
    # Check timestamp range
    now = timezone.now()
    
    # Timestamp too far in the future (more than 1 hour)
    if timestamp > now + timedelta(hours=1):
        raise ValidationError("Timestamp is too far in the future")
    
    # Timestamp too far in the past (more than 30 days)
    if timestamp < now - timedelta(days=30):
        raise ValidationError("Timestamp is too far in the past")
    
    return timestamp


# ==================== OFFER VALIDATORS ====================

def validate_offer_title(title):
    """
    Validate offer title
    """
    if not title:
        raise ValidationError("Offer title is required")
    
    if not isinstance(title, str):
        raise ValidationError("Offer title must be a string")
    
    title = title.strip()
    
    if not title:
        raise ValidationError("Offer title cannot be empty")
    
    if len(title) > MAX_OFFER_TITLE_LENGTH:
        raise ValidationError(f"Offer title cannot exceed {MAX_OFFER_TITLE_LENGTH} characters")
    
    if len(title) < 3:
        raise ValidationError("Offer title must be at least 3 characters")
    
    # Check for suspicious patterns
    suspicious_patterns = [
        r'free\s+money',
        r'click\s+here',
        r'urgent',
        r'limited\s+time',
        r'act\s+now',
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, title, re.IGNORECASE):
            logger.warning(f"Suspicious pattern in offer title: {title}")
    
    return title


def validate_offer_description(description):
    """
    Validate offer description
    """
    if not description:
        raise ValidationError("Offer description is required")
    
    if not isinstance(description, str):
        raise ValidationError("Offer description must be a string")
    
    description = description.strip()
    
    if len(description) < 10:
        raise ValidationError("Offer description must be at least 10 characters")
    
    if len(description) > 2000:
        raise ValidationError("Offer description cannot exceed 2000 characters")
    
    return description


def validate_offer_countries(countries):
    """
    Validate offer countries list
    """
    if not countries:
        raise ValidationError("Countries list is required")
    
    # Handle different input formats
    if isinstance(countries, str):
        countries = [c.strip().upper() for c in countries.split(',') if c.strip()]
    elif isinstance(countries, list):
        countries = [str(c).upper() for c in countries if c]
    else:
        raise ValidationError("Countries must be a list or comma-separated string")
    
    if not countries:
        raise ValidationError("At least one country must be specified")
    
    # Validate country codes (basic check)
    valid_country_pattern = r'^[A-Z]{2,3}$'
    for country in countries:
        if not re.match(valid_country_pattern, country):
            raise ValidationError(f"Invalid country code: {country}")
    
    return countries


# ==================== FRAUD VALIDATORS ====================

def validate_fraud_score(score):
    """
    Validate fraud score (0-100)
    """
    try:
        score = float(score)
        
        if score < 0:
            raise ValidationError("Fraud score cannot be negative")
        
        if score > 100:
            raise ValidationError("Fraud score cannot exceed 100")
        
        # Log high fraud scores
        if score >= FRAUD_SCORE_THRESHOLD:
            logger.warning(f"High fraud score detected: {score}")
        
        return score
        
    except (ValueError, TypeError):
        raise ValidationError("Fraud score must be a number")


def validate_ip_address(ip_address):
    """
    Validate IP address format
    """
    import ipaddress
    
    if not ip_address:
        raise ValidationError("IP address is required")
    
    try:
        ip = ipaddress.ip_address(ip_address)
        
        # Check for private IPs (often suspicious in conversions)
        if ip.is_private:
            logger.warning(f"Private IP address in conversion: {ip_address}")
        
        # Check for loopback IPs
        if ip.is_loopback:
            raise ValidationError("Loopback IP address not allowed")
        
        return ip_address
        
    except ValueError:
        raise ValidationError("Invalid IP address format")


# ==================== SECURITY VALIDATORS ====================

def validate_webhook_signature(payload, signature, secret):
    """
    Validate webhook signature for security
    """
    if not payload:
        raise ValidationError("Payload is required")
    
    if not signature:
        raise ValidationError("Signature is required")
    
    if not secret:
        raise ValidationError("Secret is required")
    
    # Generate expected signature
    if isinstance(payload, str):
        payload_bytes = payload.encode('utf-8')
    else:
        payload_bytes = json.dumps(payload).encode('utf-8')
    
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures securely
    if not hmac.compare_digest(signature, expected_signature):
        raise ValidationError("Invalid webhook signature")
    
    return True


def validate_rate_limit(identifier, limit, window_minutes=60):
    """
    Validate rate limiting for API endpoints
    """
    from django.core.cache import cache
    
    cache_key = f"rate_limit_{identifier}"
    
    # Get current count
    current_count = cache.get(cache_key, 0)
    
    if current_count >= limit:
        raise ValidationError(f"Rate limit exceeded. Maximum {limit} requests per {window_minutes} minutes.")
    
    # Increment counter
    cache.set(cache_key, current_count + 1, timeout=window_minutes * 60)
    
    return True


# ==================== CUSTOM VALIDATOR CLASSES ====================

class MinPayoutValidator:
    """
    Custom validator for minimum payout amounts
    """
    def __init__(self, currency='USD'):
        self.currency = currency
        self.min_amount = MIN_PAYOUT_AMOUNT
    
    def __call__(self, value):
        try:
            amount = Decimal(str(value))
            if amount < self.min_amount:
                raise ValidationError(
                    f"Minimum payout is {self.min_amount} {self.currency}"
                )
            return amount
        except (InvalidOperation, ValueError):
            raise ValidationError("Invalid payout amount")


class MaxPayoutValidator:
    """
    Custom validator for maximum payout amounts
    """
    def __init__(self, currency='USD'):
        self.currency = currency
        self.max_amount = MAX_PAYOUT_AMOUNT
    
    def __call__(self, value):
        try:
            amount = Decimal(str(value))
            if amount > self.max_amount:
                raise ValidationError(
                    f"Maximum payout is {self.max_amount} {self.currency}"
                )
            return amount
        except (InvalidOperation, ValueError):
            raise ValidationError("Invalid payout amount")


class OfferURLValidator:
    """
    Custom validator for offer URLs with security checks
    """
    def __init__(self, check_ssl=True):
        self.check_ssl = check_ssl
    
    def __call__(self, value):
        return validate_offer_url(value, self.check_ssl)


class NetworkAPIKeyValidator:
    """
    Custom validator for network API keys
    """
    def __init__(self, network_type=None):
        self.network_type = network_type
    
    def __call__(self, value):
        return validate_network_api_key(value, self.network_type)


# ==================== FILE UPLOAD VALIDATORS ====================

class FileUploadError(Exception):
    """Custom exception for file upload errors"""
    pass


class SecurityValidationError(Exception):
    """Custom exception for security validation errors"""
    pass


class FileValidator:
    """Base file validator"""
    
    def __init__(self, max_size=None, allowed_types=None, allowed_extensions=None):
        self.max_size = max_size
        self.allowed_types = allowed_types or []
        self.allowed_extensions = allowed_extensions or []
    
    def __call__(self, file):
        """Validate uploaded file"""
        if not file:
            raise ValidationError("No file provided")
        
        # Check file size
        if self.max_size and file.size > self.max_size:
            raise ValidationError(f"File size exceeds maximum limit of {self.max_size} bytes")
        
        # Check file type
        if self.allowed_types:
            import magic
            try:
                file_type = magic.from_buffer(file.read(1024), mime=True)
                if file_type not in self.allowed_types:
                    raise ValidationError(f"File type {file_type} is not allowed")
                file.seek(0)  # Reset file pointer
            except Exception as e:
                raise ValidationError(f"Could not determine file type: {str(e)}")
        
        # Check file extension
        if self.allowed_extensions:
            file_extension = file.name.split('.')[-1].lower()
            if file_extension not in self.allowed_extensions:
                raise ValidationError(f"File extension .{file_extension} is not allowed")
        
        return file


class ImageValidator(FileValidator):
    """Validator for image files"""
    
    def __init__(self, max_size=None, max_dimensions=None, min_dimensions=None):
        from .constants import ALLOWED_MIME_TYPES, IMAGE_DIMENSIONS
        super().__init__(
            max_size=max_size or FILE_SIZE_LIMITS.get('image', 5 * 1024 * 1024),
            allowed_types=ALLOWED_MIME_TYPES.get('image', []),
            allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'webp']
        )
        self.max_dimensions = max_dimensions or IMAGE_DIMENSIONS.get('large', (1200, 1200))
        self.min_dimensions = min_dimensions or IMAGE_DIMENSIONS.get('thumbnail', (150, 150))
    
    def __call__(self, file):
        """Validate image file"""
        super().__call__(file)
        
        try:
            from PIL import Image
            image = Image.open(file)
            
            # Check image dimensions
            width, height = image.size
            max_width, max_height = self.max_dimensions
            min_width, min_height = self.min_dimensions
            
            if width > max_width or height > max_height:
                raise ValidationError(f"Image dimensions {width}x{height} exceed maximum {max_width}x{max_height}")
            
            if width < min_width or height < min_height:
                raise ValidationError(f"Image dimensions {width}x{height} below minimum {min_width}x{min_height}")
            
            # Reset file pointer
            file.seek(0)
            
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Invalid image file: {str(e)}")
        
        return file


class DocumentValidator(FileValidator):
    """Validator for document files"""
    
    def __init__(self, max_size=None):
        from .constants import ALLOWED_MIME_TYPES
        super().__init__(
            max_size=max_size or FILE_SIZE_LIMITS.get('document', 10 * 1024 * 1024),
            allowed_types=ALLOWED_MIME_TYPES.get('document', []),
            allowed_extensions=['pdf', 'doc', 'docx', 'txt', 'rtf']
        )
    
    def __call__(self, file):
        """Validate document file"""
        super().__call__(file)
        
        try:
            # Additional document-specific validation
            if file.name.endswith('.pdf'):
                self._validate_pdf(file)
            elif file.name.endswith(('.doc', '.docx')):
                self._validate_word_document(file)
            
            # Reset file pointer
            file.seek(0)
            
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Invalid document file: {str(e)}")
        
        return file
    
    def _validate_pdf(self, file):
        """Validate PDF file"""
        try:
            # Read PDF header
            header = file.read(4)
            if header != b'%PDF':
                raise ValidationError("Invalid PDF file format")
            file.seek(0)
        except Exception:
            raise ValidationError("Could not validate PDF file")
    
    def _validate_word_document(self, file):
        """Validate Word document file"""
        try:
            # Basic validation for Word documents
            header = file.read(8)
            if not (header.startswith(b'PK') or b'Word' in header):
                # Word documents are ZIP files with specific structure
                pass
            file.seek(0)
        except Exception:
            raise ValidationError("Could not validate Word document")


class VideoValidator(FileValidator):
    """Validator for video files"""
    
    def __init__(self, max_size=None, max_duration=None):
        from .constants import ALLOWED_MIME_TYPES
        super().__init__(
            max_size=max_size or FILE_SIZE_LIMITS.get('video', 50 * 1024 * 1024),
            allowed_types=ALLOWED_MIME_TYPES.get('video', []),
            allowed_extensions=['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm']
        )
        self.max_duration = max_duration
    
    def __call__(self, file):
        """Validate video file"""
        super().__call__(file)
        
        if self.max_duration:
            try:
                import cv2
                video = cv2.VideoCapture(file.name)
                fps = video.get(cv2.CAP_PROP_FPS)
                frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
                duration = frame_count / fps if fps > 0 else 0
                
                if duration > self.max_duration:
                    raise ValidationError(f"Video duration {duration:.2f}s exceeds maximum {self.max_duration}s")
                
                video.release()
                file.seek(0)
                
            except Exception as e:
                if isinstance(e, ValidationError):
                    raise
                # If video validation fails, still allow the file
                pass
        
        return file


class AudioValidator(FileValidator):
    """Validator for audio files"""
    
    def __init__(self, max_size=None, max_duration=None):
        from .constants import ALLOWED_MIME_TYPES
        super().__init__(
            max_size=max_size or FILE_SIZE_LIMITS.get('audio', 10 * 1024 * 1024),
            allowed_types=ALLOWED_MIME_TYPES.get('audio', []),
            allowed_extensions=['mp3', 'wav', 'ogg', 'flac', 'aac']
        )
        self.max_duration = max_duration
    
    def __call__(self, file):
        """Validate audio file"""
        super().__call__(file)
        
        if self.max_duration:
            try:
                import mutagen
                audio_file = mutagen.File(file)
                if audio_file and hasattr(audio_file, 'info'):
                    duration = audio_file.info.length
                    if duration > self.max_duration:
                        raise ValidationError(f"Audio duration {duration:.2f}s exceeds maximum {self.max_duration}s")
                
                file.seek(0)
                
            except Exception as e:
                if isinstance(e, ValidationError):
                    raise
                # If audio validation fails, still allow the file
                pass
        
        return file


# ==================== SECURITY VALIDATORS ====================

class ContentSecurityValidator:
    """Validator for content security"""
    
    def __init__(self, enable_virus_scan=False, enable_content_scan=True):
        self.enable_virus_scan = enable_virus_scan
        self.enable_content_scan = enable_content_scan
    
    def validate_file(self, file):
        """Validate file for security threats"""
        if self.enable_virus_scan:
            self._scan_for_viruses(file)
        
        if self.enable_content_scan:
            self._scan_content(file)
        
        return file
    
    def _scan_for_viruses(self, file):
        """Scan file for viruses"""
        try:
            # Integrate with antivirus solution
            # This is a placeholder for actual virus scanning
            import hashlib
            file_hash = hashlib.md5()
            for chunk in file.chunks():
                file_hash.update(chunk)
            
            # Check against known malicious hashes
            file.seek(0)
            
        except Exception as e:
            logger.warning(f"Virus scan failed: {str(e)}")
    
    def _scan_content(self, file):
        """Scan file content for threats"""
        try:
            # Check for malicious content patterns
            file_content = file.read(1024 * 1024)  # Read first 1MB
            file.seek(0)
            
            # Add content scanning logic here
            suspicious_patterns = [
                b'<script',
                b'javascript:',
                b'eval(',
                b'document.cookie',
            ]
            
            for pattern in suspicious_patterns:
                if pattern in file_content.lower():
                    raise SecurityValidationError(f"Suspicious content detected: {pattern.decode()}")
            
        except Exception as e:
            logger.warning(f"Content scan failed: {str(e)}")


class RateLimitValidator:
    """Validator for rate limiting"""
    
    def __init__(self, max_requests=100, window=3600):
        self.max_requests = max_requests
        self.window = window
    
    def validate_request(self, request):
        """Validate request against rate limits"""
        from django.core.cache import cache
        import time
        
        user_id = request.user.id if request.user.is_authenticated else request.META.get('REMOTE_ADDR')
        key = f"rate_limit_{user_id}"
        
        # Get current request count
        requests = cache.get(key, [])
        now = int(time.time())
        
        # Remove old requests outside window
        requests = [req_time for req_time in requests if now - req_time < self.window]
        
        # Check if limit exceeded
        if len(requests) >= self.max_requests:
            raise ValidationError(f"Rate limit exceeded. Maximum {self.max_requests} requests per {self.window} seconds.")
        
        # Add current request
        requests.append(now)
        cache.set(key, requests, self.window)
        
        return True
