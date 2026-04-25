"""
Validators for Offer Routing System
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .choices import RouteOperator, CapType, FallbackType, PersonalizationAlgorithm
from .enums import DeviceType, OSType, BrowserType


def validate_route_name(value):
    """Validate route name."""
    if not value or not isinstance(value, str):
        raise ValidationError(_('Route name is required and must be a string'))
    
    if len(value.strip()) < 3:
        raise ValidationError(_('Route name must be at least 3 characters long'))
    
    if len(value) > 100:
        raise ValidationError(_('Route name cannot exceed 100 characters'))
    
    # Check for invalid characters
    invalid_chars = ['<', '>', '&', '"', "'", '\\', '/', '?']
    if any(char in value for char in invalid_chars):
        raise ValidationError(_('Route name contains invalid characters'))
    
    return value.strip()


def validate_priority(value):
    """Validate route priority."""
    if not isinstance(value, int):
        raise ValidationError(_('Priority must be an integer'))
    
    if value < 1 or value > 10:
        raise ValidationError(_('Priority must be between 1 and 10'))
    
    return value


def validate_condition_value(value, operator, field_type):
    """Validate condition value based on operator and field type."""
    if value is None:
        raise ValidationError(_('Condition value is required'))
    
    # String validations
    if operator in [RouteOperator.EQUALS, RouteOperator.NOT_EQUALS, 
                    RouteOperator.CONTAINS, RouteOperator.NOT_CONTAINS,
                    RouteOperator.STARTS_WITH, RouteOperator.ENDS_WITH]:
        if not isinstance(value, str):
            raise ValidationError(_('Value must be a string for this operator'))
        
        if len(value) > 500:
            raise ValidationError(_('String value cannot exceed 500 characters'))
    
    # Numeric validations
    elif operator in [RouteOperator.GREATER_THAN, RouteOperator.LESS_THAN,
                    RouteOperator.GREATER_EQUAL, RouteOperator.LESS_EQUAL]:
        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
            raise ValidationError(_('Value must be a number for this operator'))
        
        if field_type == 'percentage' and (numeric_value < 0 or numeric_value > 100):
            raise ValidationError(_('Percentage value must be between 0 and 100'))
    
    # List validations
    elif operator in [RouteOperator.IN, RouteOperator.NOT_IN]:
        if not isinstance(value, (list, tuple)):
            raise ValidationError(_('Value must be a list for this operator'))
        
        if len(value) > 100:
            raise ValidationError(_('List cannot contain more than 100 items'))
        
        for item in value:
            if not isinstance(item, (str, int, float)):
                raise ValidationError(_('List items must be strings or numbers'))
    
    return value


def validate_device_type(value):
    """Validate device type."""
    if not isinstance(value, str):
        raise ValidationError(_('Device type must be a string'))
    
    valid_devices = [DeviceType.MOBILE, DeviceType.DESKTOP, DeviceType.TABLET,
                    DeviceType.SMART_TV, DeviceType.WEARABLE, DeviceType.GAME_CONSOLE]
    
    if value not in valid_devices:
        raise ValidationError(_('Invalid device type. Must be one of: {}').format(', '.join(valid_devices)))
    
    return value


def validate_os_type(value):
    """Validate operating system type."""
    if not isinstance(value, str):
        raise ValidationError(_('OS type must be a string'))
    
    valid_os = [OSType.IOS, OSType.ANDROID, OSType.WINDOWS, OSType.MACOS,
                OSType.LINUX, OSType.CHROME_OS]
    
    if value not in valid_os:
        raise ValidationError(_('Invalid OS type. Must be one of: {}').format(', '.join(valid_os)))
    
    return value


def validate_browser_type(value):
    """Validate browser type."""
    if not isinstance(value, str):
        raise ValidationError(_('Browser type must be a string'))
    
    valid_browsers = [BrowserType.CHROME, BrowserType.SAFARI, BrowserType.FIREFOX,
                     BrowserType.EDGE, BrowserType.OPERA, BrowserType.INTERNET_EXPLORER]
    
    if value not in valid_browsers:
        raise ValidationError(_('Invalid browser type. Must be one of: {}').format(', '.join(valid_browsers)))
    
    return value


def validate_cap_value(value, cap_type):
    """Validate cap value based on cap type."""
    if not isinstance(value, (int, float)):
        raise ValidationError(_('Cap value must be a number'))
    
    if value < 0:
        raise ValidationError(_('Cap value must be positive'))
    
    if cap_type == CapType.PERCENTAGE and value > 100:
        raise ValidationError(_('Percentage cap cannot exceed 100'))
    
    return value


def validate_split_percentage(value):
    """Validate A/B test split percentage."""
    if not isinstance(value, (int, float)):
        raise ValidationError(_('Split percentage must be a number'))
    
    if value < 1 or value > 99:
        raise ValidationError(_('Split percentage must be between 1 and 99'))
    
    return value


def validate_fallback_type(value):
    """Validate fallback type."""
    if not isinstance(value, str):
        raise ValidationError(_('Fallback type must be a string'))
    
    valid_types = [FallbackType.CATEGORY, FallbackType.NETWORK, FallbackType.DEFAULT,
                   FallbackType.PROMOTION, FallbackType.HIDE_SECTION]
    
    if value not in valid_types:
        raise ValidationError(_('Invalid fallback type. Must be one of: {}').format(', '.join(valid_types)))
    
    return value


def validate_personalization_algorithm(value):
    """Validate personalization algorithm."""
    if not isinstance(value, str):
        raise ValidationError(_('Personalization algorithm must be a string'))
    
    valid_algorithms = [PersonalizationAlgorithm.COLLABORATIVE,
                       PersonalizationAlgorithm.CONTENT_BASED,
                       PersonalizationAlgorithm.HYBRID,
                       PersonalizationAlgorithm.RULE_BASED,
                       PersonalizationAlgorithm.MACHINE_LEARNING]
    
    if value not in valid_algorithms:
        raise ValidationError(_('Invalid algorithm. Must be one of: {}').format(', '.join(valid_algorithms)))
    
    return value


def validate_score_weights(weights_dict):
    """Validate score weights dictionary."""
    if not isinstance(weights_dict, dict):
        raise ValidationError(_('Score weights must be a dictionary'))
    
    required_keys = ['epc', 'cr', 'relevance', 'freshness']
    
    for key in required_keys:
        if key not in weights_dict:
            raise ValidationError(_('Missing required weight: {}').format(key))
        
        if not isinstance(weights_dict[key], (int, float)):
            raise ValidationError(_('Weight {} must be a number').format(key))
        
        if weights_dict[key] < 0 or weights_dict[key] > 1:
            raise ValidationError(_('Weight {} must be between 0 and 1').format(key))
    
    # Check if weights sum to 1 (or close to it)
    total_weight = sum(weights_dict.values())
    if abs(total_weight - 1.0) > 0.1:
        raise ValidationError(_('Weights should sum to 1.0 (current: {})').format(total_weight))
    
    return weights_dict


def validate_time_window(days):
    """Validate time window in days."""
    if not isinstance(days, int):
        raise ValidationError(_('Time window must be an integer'))
    
    if days < 1 or days > 365:
        raise ValidationError(_('Time window must be between 1 and 365 days'))
    
    return days


def validate_geo_targeting(geo_data):
    """Validate geographic targeting data."""
    if not isinstance(geo_data, dict):
        raise ValidationError(_('Geo targeting data must be a dictionary'))
    
    # Validate country codes
    if 'countries' in geo_data:
        countries = geo_data['countries']
        if not isinstance(countries, (list, tuple)):
            raise ValidationError(_('Countries must be a list'))
        
        for country in countries:
            if not isinstance(country, str) or len(country) != 2:
                raise ValidationError(_('Country codes must be 2-character strings'))
    
    # Validate regions
    if 'regions' in geo_data:
        regions = geo_data['regions']
        if not isinstance(regions, (list, tuple)):
            raise ValidationError(_('Regions must be a list'))
        
        for region in regions:
            if not isinstance(region, str) or len(region) > 100:
                raise ValidationError(_('Region names must be strings under 100 characters'))
    
    return geo_data


def validate_behavioral_data(behavior_data):
    """Validate behavioral targeting data."""
    if not isinstance(behavior_data, dict):
        raise ValidationError(_('Behavioral data must be a dictionary'))
    
    # Validate event types
    if 'event_types' in behavior_data:
        event_types = behavior_data['event_types']
        if not isinstance(event_types, (list, tuple)):
            raise ValidationError(_('Event types must be a list'))
        
        valid_events = ['page_view', 'click', 'purchase', 'add_to_cart', 'search', 'login', 'signup']
        for event_type in event_types:
            if event_type not in valid_events:
                raise ValidationError(_('Invalid event type: {}').format(event_type))
    
    # Validate thresholds
    if 'thresholds' in behavior_data:
        thresholds = behavior_data['thresholds']
        if not isinstance(thresholds, dict):
            raise ValidationError(_('Thresholds must be a dictionary'))
        
        for key, value in thresholds.items():
            if not isinstance(value, (int, float)) or value < 0:
                raise ValidationError(_('Threshold {} must be a positive number').format(key))
    
    return behavior_data


def validate_preference_vector(vector_data):
    """Validate user preference vector."""
    if not isinstance(vector_data, dict):
        raise ValidationError(_('Preference vector must be a dictionary'))
    
    # Check maximum size
    if len(vector_data) > 100:
        raise ValidationError(_('Preference vector cannot exceed 100 categories'))
    
    # Validate weights
    for category, weight in vector_data.items():
        if not isinstance(category, str) or len(category) > 50:
            raise ValidationError(_('Category names must be strings under 50 characters'))
        
        if not isinstance(weight, (int, float)) or weight < 0 or weight > 1:
            raise ValidationError(_('Weights must be numbers between 0 and 1'))
    
    return vector_data


def validate_cache_config(config_data):
    """Validate cache configuration."""
    if not isinstance(config_data, dict):
        raise ValidationError(_('Cache config must be a dictionary'))
    
    required_keys = ['timeout', 'max_size', 'strategy']
    
    for key in required_keys:
        if key not in config_data:
            raise ValidationError(_('Missing cache config: {}').format(key))
    
    # Validate timeout
    timeout = config_data.get('timeout')
    if not isinstance(timeout, int) or timeout < 1 or timeout > 86400:
        raise ValidationError(_('Cache timeout must be between 1 and 86400 seconds'))
    
    # Validate max_size
    max_size = config_data.get('max_size')
    if not isinstance(max_size, int) or max_size < 1 or max_size > 1000000:
        raise ValidationError(_('Cache max size must be between 1 and 1000000'))
    
    return config_data


def validate_ab_test_config(config_data):
    """Validate A/B test configuration."""
    if not isinstance(config_data, dict):
        raise ValidationError(_('A/B test config must be a dictionary'))
    
    required_keys = ['name', 'control_route', 'variant_route', 'split_percentage']
    
    for key in required_keys:
        if key not in config_data:
            raise ValidationError(_('Missing A/B test config: {}').format(key))
    
    # Validate split percentage
    split_pct = config_data.get('split_percentage')
    if not isinstance(split_pct, (int, float)) or split_pct < 1 or split_pct > 99:
        raise ValidationError(_('Split percentage must be between 1 and 99'))
    
    # Validate duration
    if 'duration_hours' in config_data:
        duration = config_data['duration_hours']
        if not isinstance(duration, int) or duration < 1 or duration > 720:
            raise ValidationError(_('Duration must be between 1 and 720 hours'))
    
    return config_data


def validate_routing_config(config_data):
    """Validate overall routing configuration."""
    if not isinstance(config_data, dict):
        raise ValidationError(_('Routing config must be a dictionary'))
    
    # Validate max routing time
    if 'max_routing_time_ms' in config_data:
        max_time = config_data['max_routing_time_ms']
        if not isinstance(max_time, int) or max_time < 10 or max_time > 1000:
            raise ValidationError(_('Max routing time must be between 10 and 1000ms'))
    
    # Validate cache settings
    if 'cache_enabled' in config_data:
        cache_enabled = config_data['cache_enabled']
        if not isinstance(cache_enabled, bool):
            raise ValidationError(_('Cache enabled must be a boolean'))
    
    # Validate personalization settings
    if 'personalization_enabled' in config_data:
        personalization_enabled = config_data['personalization_enabled']
        if not isinstance(personalization_enabled, bool):
            raise ValidationError(_('Personalization enabled must be a boolean'))
    
    return config_data


def validate_api_key_format(api_key):
    """Validate API key format."""
    if not isinstance(api_key, str):
        raise ValidationError(_('API key must be a string'))
    
    if len(api_key) < 20 or len(api_key) > 100:
        raise ValidationError(_('API key must be between 20 and 100 characters'))
    
    # Check for valid characters (alphanumeric + some special chars)
    import re
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', api_key):
        raise ValidationError(_('API key contains invalid characters'))
    
    return api_key


def validate_json_field(value):
    """Validate JSON field data."""
    if value is None:
        return None
    
    try:
        import json
        parsed_value = json.loads(value) if isinstance(value, str) else value
    except (json.JSONDecodeError, TypeError):
        raise ValidationError(_('Invalid JSON format'))
    
    # Check maximum size
    json_str = json.dumps(parsed_value)
    if len(json_str) > 10000:
        raise ValidationError(_('JSON data too large (max 10KB)'))
    
    return parsed_value


def validate_email_list(emails):
    """Validate list of email addresses."""
    if not isinstance(emails, (list, tuple)):
        raise ValidationError(_('Email list must be a list'))
    
    if len(emails) > 100:
        raise ValidationError(_('Email list cannot exceed 100 addresses'))
    
    for email in emails:
        if not isinstance(email, str):
            raise ValidationError(_('Email addresses must be strings'))
        
        # Basic email validation
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ValidationError(_('Invalid email address: {}').format(email))
    
    return emails


def validate_url_list(urls):
    """Validate list of URLs."""
    if not isinstance(urls, (list, tuple)):
        raise ValidationError(_('URL list must be a list'))
    
    if len(urls) > 50:
        raise ValidationError(_('URL list cannot exceed 50 URLs'))
    
    for url in urls:
        if not isinstance(url, str):
            raise ValidationError(_('URLs must be strings'))
        
        # Basic URL validation
        from django.core.validators import URLValidator
        validator = URLValidator()
        try:
            validator(url)
        except ValidationError:
            raise ValidationError(_('Invalid URL: {}').format(url))
    
    return urls


def validate_date_range(start_date, end_date):
    """Validate date range."""
    if start_date and end_date:
        if start_date > end_date:
            raise ValidationError(_('Start date cannot be after end date'))
        
        # Check if range is reasonable
        from datetime import timedelta
        if end_date - start_date > timedelta(days=365):
            raise ValidationError(_('Date range cannot exceed 1 year'))
    
    return {'start_date': start_date, 'end_date': end_date}


def validate_score_range(score, min_score=0, max_score=100):
    """Validate score range."""
    if not isinstance(score, (int, float)):
        raise ValidationError(_('Score must be a number'))
    
    if score < min_score or score > max_score:
        raise ValidationError(_('Score must be between {} and {}').format(min_score, max_score))
    
    return score


def validate_percentage_value(value, field_name):
    """Validate percentage value."""
    if not isinstance(value, (int, float)):
        raise ValidationError(_('{} must be a number').format(field_name))
    
    if value < 0 or value > 100:
        raise ValidationError(_('{} must be between 0 and 100').format(field_name))
    
    return value


def validate_json_schema(data, schema):
    """Validate data against JSON schema."""
    if not isinstance(data, dict):
        raise ValidationError(_('Data must be a dictionary'))
    
    # Basic schema validation (would use jsonschema library in production)
    required_fields = schema.get('required', [])
    for field in required_fields:
        if field not in data:
            raise ValidationError(_('Missing required field: {}').format(field))
    
    # Validate field types
    field_types = schema.get('field_types', {})
    for field, expected_type in field_types.items():
        if field in data:
            if not isinstance(data[field], expected_type):
                raise ValidationError(_('Field {} must be of type {}').format(field, expected_type.__name__))
    
    return data
