"""
Backup Module Validators
Validation functions for backup configurations and operations
"""

import re
from datetime import datetime, timedelta
from croniter import croniter
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings


def validate_backup_schedule(cron_expression):
    """
    Validate cron expression for backup scheduling
    
    Args:
        cron_expression (str): Cron expression to validate
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If cron expression is invalid
    """
    if not cron_expression:
        raise ValidationError("Cron expression cannot be empty")
    
    try:
        # Test if cron expression is valid
        croniter(cron_expression)
        
        # Additional validation for common patterns
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValidationError(
                "Cron expression must have 5 parts: minute hour day month weekday"
            )
        
        # Validate minute (0-59)
        minute_part = parts[0]
        if not _validate_cron_part(minute_part, 0, 59):
            raise ValidationError(f"Invalid minute part: {minute_part}")
        
        # Validate hour (0-23)
        hour_part = parts[1]
        if not _validate_cron_part(hour_part, 0, 23):
            raise ValidationError(f"Invalid hour part: {hour_part}")
        
        # Validate day (1-31)
        day_part = parts[2]
        if not _validate_cron_part(day_part, 1, 31):
            raise ValidationError(f"Invalid day part: {day_part}")
        
        # Validate month (1-12)
        month_part = parts[3]
        if not _validate_cron_part(month_part, 1, 12):
            raise ValidationError(f"Invalid month part: {month_part}")
        
        # Validate weekday (0-7, where 0 and 7 are Sunday)
        weekday_part = parts[4]
        if not _validate_cron_part(weekday_part, 0, 7):
            raise ValidationError(f"Invalid weekday part: {weekday_part}")
        
        return True
        
    except ValueError as e:
        raise ValidationError(f"Invalid cron expression: {str(e)}")
    except Exception as e:
        raise ValidationError(f"Cron expression validation failed: {str(e)}")


def _validate_cron_part(part, min_val, max_val):
    """
    Validate individual cron part
    
    Args:
        part (str): Cron part to validate
        min_val (int): Minimum allowed value
        max_val (int): Maximum allowed value
        
    Returns:
        bool: True if valid
    """
    if part == '*':
        return True
    
    # Handle step values (e.g., */5)
    if '*/' in part:
        try:
            step = int(part.split('*/')[1])
            return 1 <= step <= (max_val - min_val + 1)
        except ValueError:
            return False
    
    # Handle ranges (e.g., 1-5)
    if '-' in part:
        try:
            start, end = part.split('-')
            start_val = int(start)
            end_val = int(end)
            return min_val <= start_val <= max_val and min_val <= end_val <= max_val and start_val <= end_val
        except ValueError:
            return False
    
    # Handle comma-separated values (e.g., 1,2,3)
    if ',' in part:
        try:
            values = [int(v) for v in part.split(',')]
            return all(min_val <= v <= max_val for v in values)
        except ValueError:
            return False
    
    # Handle single value
    try:
        value = int(part)
        return min_val <= value <= max_val
    except ValueError:
        return False


def validate_retention_period(days):
    """
    Validate retention period for backup retention
    
    Args:
        days (int): Number of days for retention
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If retention period is invalid
    """
    if not isinstance(days, int):
        raise ValidationError("Retention period must be an integer")
    
    if days < 1:
        raise ValidationError("Retention period must be at least 1 day")
    
    if days > 365:
        raise ValidationError("Retention period cannot exceed 365 days")
    
    return True


def validate_storage_credentials(storage_type, credentials):
    """
    Validate storage credentials for different storage types
    
    Args:
        storage_type (str): Type of storage (s3, gcs, azure, local)
        credentials (dict): Dictionary containing credentials
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If credentials are invalid
    """
    if storage_type == 'local':
        return _validate_local_credentials(credentials)
    elif storage_type == 's3':
        return _validate_s3_credentials(credentials)
    elif storage_type == 'gcs':
        return _validate_gcs_credentials(credentials)
    elif storage_type == 'azure':
        return _validate_azure_credentials(credentials)
    else:
        raise ValidationError(f"Unsupported storage type: {storage_type}")


def _validate_local_credentials(credentials):
    """Validate local storage credentials"""
    if not isinstance(credentials, dict):
        raise ValidationError("Local storage credentials must be a dictionary")
    
    # Local storage typically needs just a path
    if 'path' in credentials:
        path = credentials['path']
        if not isinstance(path, str):
            raise ValidationError("Local storage path must be a string")
        if not path.strip():
            raise ValidationError("Local storage path cannot be empty")
    
    return True


def _validate_s3_credentials(credentials):
    """Validate AWS S3 credentials"""
    if not isinstance(credentials, dict):
        raise ValidationError("S3 credentials must be a dictionary")
    
    required_fields = ['access_key', 'secret_key', 'bucket_name']
    for field in required_fields:
        if field not in credentials:
            raise ValidationError(f"S3 credentials missing required field: {field}")
        if not isinstance(credentials[field], str):
            raise ValidationError(f"S3 {field} must be a string")
        if not credentials[field].strip():
            raise ValidationError(f"S3 {field} cannot be empty")
    
    # Optional fields validation
    if 'region' in credentials:
        region = credentials['region']
        if not isinstance(region, str):
            raise ValidationError("S3 region must be a string")
        
        # Validate AWS region format
        aws_regions = [
            'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
            'ca-central-1', 'eu-west-1', 'eu-west-2', 'eu-central-1',
            'ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1',
            'ap-northeast-2', 'ap-south-1', 'sa-east-1'
        ]
        if region not in aws_regions:
            raise ValidationError(f"Invalid AWS region: {region}")
    
    return True


def _validate_gcs_credentials(credentials):
    """Validate Google Cloud Storage credentials"""
    if not isinstance(credentials, dict):
        raise ValidationError("GCS credentials must be a dictionary")
    
    required_fields = ['project_id', 'bucket_name', 'credentials_file']
    for field in required_fields:
        if field not in credentials:
            raise ValidationError(f"GCS credentials missing required field: {field}")
    
    # Validate project_id
    project_id = credentials['project_id']
    if not isinstance(project_id, str):
        raise ValidationError("GCS project_id must be a string")
    if not project_id.strip():
        raise ValidationError("GCS project_id cannot be empty")
    
    # Validate bucket_name
    bucket_name = credentials['bucket_name']
    if not isinstance(bucket_name, str):
        raise ValidationError("GCS bucket_name must be a string")
    if not bucket_name.strip():
        raise ValidationError("GCS bucket_name cannot be empty")
    
    # Validate bucket name format (GCS naming rules)
    if not re.match(r'^[a-z0-9._-]{3,63}$', bucket_name):
        raise ValidationError(
            "GCS bucket name must be 3-63 characters, lowercase, "
            "and can contain hyphens, underscores, and dots"
        )
    
    # Validate credentials file path
    credentials_file = credentials['credentials_file']
    if not isinstance(credentials_file, str):
        raise ValidationError("GCS credentials_file must be a string")
    if not credentials_file.strip():
        raise ValidationError("GCS credentials_file cannot be empty")
    
    return True


def _validate_azure_credentials(credentials):
    """Validate Azure Blob Storage credentials"""
    if not isinstance(credentials, dict):
        raise ValidationError("Azure credentials must be a dictionary")
    
    required_fields = ['account_name', 'account_key', 'container_name']
    for field in required_fields:
        if field not in credentials:
            raise ValidationError(f"Azure credentials missing required field: {field}")
        if not isinstance(credentials[field], str):
            raise ValidationError(f"Azure {field} must be a string")
        if not credentials[field].strip():
            raise ValidationError(f"Azure {field} cannot be empty")
    
    # Validate account name format
    account_name = credentials['account_name']
    if not re.match(r'^[a-z0-9]{3,24}$', account_name):
        raise ValidationError(
            "Azure account name must be 3-24 characters, lowercase letters and numbers only"
        )
    
    # Validate container name format
    container_name = credentials['container_name']
    if not re.match(r'^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$', container_name):
        raise ValidationError(
            "Azure container name must be 3-63 characters, lowercase, "
            "can contain hyphens, but cannot start or end with hyphen"
        )
    
    return True


def validate_restore_target(database_config):
    """
    Validate database connection for restore target
    
    Args:
        database_config (dict): Database configuration for restore
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If database configuration is invalid
    """
    if not isinstance(database_config, dict):
        raise ValidationError("Database configuration must be a dictionary")
    
    # Required fields for all database types
    required_fields = ['engine', 'name']
    for field in required_fields:
        if field not in database_config:
            raise ValidationError(f"Database config missing required field: {field}")
    
    engine = database_config['engine']
    
    if engine == 'postgresql':
        return _validate_postgresql_config(database_config)
    elif engine == 'mysql':
        return _validate_mysql_config(database_config)
    elif engine == 'sqlite':
        return _validate_sqlite_config(database_config)
    else:
        raise ValidationError(f"Unsupported database engine: {engine}")


def _validate_postgresql_config(config):
    """Validate PostgreSQL configuration"""
    required_fields = ['host', 'port', 'user', 'password']
    for field in required_fields:
        if field not in config:
            raise ValidationError(f"PostgreSQL config missing required field: {field}")
    
    # Validate host
    host = config['host']
    if not isinstance(host, str):
        raise ValidationError("PostgreSQL host must be a string")
    
    # Validate port
    port = config['port']
    try:
        port_int = int(port)
        if not (1 <= port_int <= 65535):
            raise ValidationError("PostgreSQL port must be between 1 and 65535")
    except ValueError:
        raise ValidationError("PostgreSQL port must be a valid integer")
    
    # Validate user and password
    if not isinstance(config['user'], str) or not config['user'].strip():
        raise ValidationError("PostgreSQL user cannot be empty")
    
    if not isinstance(config['password'], str) or not config['password'].strip():
        raise ValidationError("PostgreSQL password cannot be empty")
    
    return True


def _validate_mysql_config(config):
    """Validate MySQL configuration"""
    required_fields = ['host', 'port', 'user', 'password']
    for field in required_fields:
        if field not in config:
            raise ValidationError(f"MySQL config missing required field: {field}")
    
    # Similar validation to PostgreSQL
    host = config['host']
    if not isinstance(host, str):
        raise ValidationError("MySQL host must be a string")
    
    port = config['port']
    try:
        port_int = int(port)
        if not (1 <= port_int <= 65535):
            raise ValidationError("MySQL port must be between 1 and 65535")
    except ValueError:
        raise ValidationError("MySQL port must be a valid integer")
    
    if not isinstance(config['user'], str) or not config['user'].strip():
        raise ValidationError("MySQL user cannot be empty")
    
    if not isinstance(config['password'], str) or not config['password'].strip():
        raise ValidationError("MySQL password cannot be empty")
    
    return True


def _validate_sqlite_config(config):
    """Validate SQLite configuration"""
    database_path = config.get('name')
    if not isinstance(database_path, str):
        raise ValidationError("SQLite database path must be a string")
    
    if not database_path.strip():
        raise ValidationError("SQLite database path cannot be empty")
    
    # Check if directory exists (optional validation)
    import os
    db_dir = os.path.dirname(database_path)
    if db_dir and not os.path.exists(db_dir):
        raise ValidationError(f"SQLite database directory does not exist: {db_dir}")
    
    return True


def validate_backup_name(name):
    """
    Validate backup name
    
    Args:
        name (str): Backup name to validate
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If backup name is invalid
    """
    if not isinstance(name, str):
        raise ValidationError("Backup name must be a string")
    
    if not name.strip():
        raise ValidationError("Backup name cannot be empty")
    
    if len(name) > 255:
        raise ValidationError("Backup name cannot exceed 255 characters")
    
    # Check for invalid characters
    if re.search(r'[<>:"/\\|?*]', name):
        raise ValidationError("Backup name contains invalid characters")
    
    return True


def validate_compression_level(level, method='gzip'):
    """
    Validate compression level
    
    Args:
        level (int): Compression level
        method (str): Compression method
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If compression level is invalid
    """
    if not isinstance(level, int):
        raise ValidationError("Compression level must be an integer")
    
    compression_ranges = {
        'gzip': (1, 9),
        'bzip2': (1, 9),
        'lzma': (0, 9),
        'zstd': (1, 22),
        'zip': (0, 9)
    }
    
    if method not in compression_ranges:
        raise ValidationError(f"Unsupported compression method: {method}")
    
    min_level, max_level = compression_ranges[method]
    
    if not (min_level <= level <= max_level):
        raise ValidationError(
            f"Compression level for {method} must be between {min_level} and {max_level}"
        )
    
    return True


def validate_encryption_algorithm(algorithm):
    """
    Validate encryption algorithm
    
    Args:
        algorithm (str): Encryption algorithm to validate
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If encryption algorithm is invalid
    """
    if not isinstance(algorithm, str):
        raise ValidationError("Encryption algorithm must be a string")
    
    valid_algorithms = [
        'AES-256-GCM',
        'AES-256-CBC',
        'ChaCha20-Poly1305',
        'Fernet'
    ]
    
    if algorithm not in valid_algorithms:
        raise ValidationError(
            f"Invalid encryption algorithm. Valid options: {', '.join(valid_algorithms)}"
        )
    
    return True


def validate_file_size(size_bytes):
    """
    Validate file size
    
    Args:
        size_bytes (int): File size in bytes
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If file size is invalid
    """
    if not isinstance(size_bytes, (int, float)):
        raise ValidationError("File size must be a number")
    
    if size_bytes < 0:
        raise ValidationError("File size cannot be negative")
    
    max_size = getattr(settings, 'MAX_BACKUP_SIZE', 10 * 1024 * 1024 * 1024)  # 10GB default
    if size_bytes > max_size:
        raise ValidationError(
            f"File size exceeds maximum allowed size of {max_size} bytes"
        )
    
    return True


def validate_backup_type(backup_type):
    """
    Validate backup type
    
    Args:
        backup_type (str): Backup type to validate
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If backup type is invalid
    """
    if not isinstance(backup_type, str):
        raise ValidationError("Backup type must be a string")
    
    valid_types = [
        'full', 'incremental', 'differential', 'delta',
        'partial', 'schema_only', 'data_only',
        'scheduled', 'manual', 'automated'
    ]
    
    if backup_type not in valid_types:
        raise ValidationError(
            f"Invalid backup type. Valid options: {', '.join(valid_types)}"
        )
    
    return True


def validate_storage_type(storage_type):
    """
    Validate storage type
    
    Args:
        storage_type (str): Storage type to validate
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If storage type is invalid
    """
    if not isinstance(storage_type, str):
        raise ValidationError("Storage type must be a string")
    
    valid_types = [
        'local', 's3', 'gcs', 'azure', 'ftp', 'sftp',
        'dropbox', 'multi', 'redundant'
    ]
    
    if storage_type not in valid_types:
        raise ValidationError(
            f"Invalid storage type. Valid options: {', '.join(valid_types)}"
        )
    
    return True


def validate_backup_frequency(frequency):
    """
    Validate backup frequency
    
    Args:
        frequency (str): Frequency to validate
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If frequency is invalid
    """
    if not isinstance(frequency, str):
        raise ValidationError("Backup frequency must be a string")
    
    valid_frequencies = [
        'hourly', 'daily', 'weekly', 'monthly', 'custom'
    ]
    
    if frequency not in valid_frequencies:
        raise ValidationError(
            f"Invalid backup frequency. Valid options: {', '.join(valid_frequencies)}"
        )
    
    return True


def validate_notification_channels(channels):
    """
    Validate notification channels
    
    Args:
        channels (list): List of notification channels
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If notification channels are invalid
    """
    if not isinstance(channels, (list, tuple)):
        raise ValidationError("Notification channels must be a list or tuple")
    
    valid_channels = [
        'email', 'sms', 'slack', 'telegram', 'webhook',
        'push', 'in_app', 'console'
    ]
    
    for channel in channels:
        if not isinstance(channel, str):
            raise ValidationError("Each notification channel must be a string")
        
        if channel not in valid_channels:
            raise ValidationError(
                f"Invalid notification channel: {channel}. "
                f"Valid options: {', '.join(valid_channels)}"
            )
    
    return True


def validate_backup_tags(tags):
    """
    Validate backup tags
    
    Args:
        tags (list): List of backup tags
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If tags are invalid
    """
    if not isinstance(tags, (list, tuple)):
        raise ValidationError("Backup tags must be a list or tuple")
    
    for tag in tags:
        if not isinstance(tag, str):
            raise ValidationError("Each backup tag must be a string")
        
        if not tag.strip():
            raise ValidationError("Backup tags cannot be empty strings")
        
        if len(tag) > 50:
            raise ValidationError("Backup tags cannot exceed 50 characters")
        
        if re.search(r'[<>:"/\\|?*]', tag):
            raise ValidationError(f"Backup tag '{tag}' contains invalid characters")
    
    return True


def validate_database_name(name):
    """
    Validate database name
    
    Args:
        name (str): Database name to validate
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If database name is invalid
    """
    if not isinstance(name, str):
        raise ValidationError("Database name must be a string")
    
    if not name.strip():
        raise ValidationError("Database name cannot be empty")
    
    if len(name) > 64:
        raise ValidationError("Database name cannot exceed 64 characters")
    
    # Check for valid database name characters
    if not re.match(r'^[a-zA-Z0-9_]+$', name):
        raise ValidationError(
            "Database name can only contain letters, numbers, and underscores"
        )
    
    return True


def validate_table_list(tables):
    """
    Validate list of table names
    
    Args:
        tables (list): List of table names
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If table names are invalid
    """
    if not isinstance(tables, (list, tuple)):
        raise ValidationError("Table list must be a list or tuple")
    
    if len(tables) > 1000:
        raise ValidationError("Cannot include more than 1000 tables in a single backup")
    
    for table in tables:
        if not isinstance(table, str):
            raise ValidationError("Each table name must be a string")
        
        if not table.strip():
            raise ValidationError("Table names cannot be empty strings")
        
        if len(table) > 64:
            raise ValidationError("Table names cannot exceed 64 characters")
        
        # Check for valid table name characters (allow dots for schema.table)
        if not re.match(r'^[a-zA-Z0-9_.]+$', table):
            raise ValidationError(
                f"Table name '{table}' contains invalid characters"
            )
    
    return True


def validate_backup_metadata(metadata):
    """
    Validate backup metadata
    
    Args:
        metadata (dict): Backup metadata dictionary
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If metadata is invalid
    """
    if not isinstance(metadata, dict):
        raise ValidationError("Backup metadata must be a dictionary")
    
    # Check metadata size limit
    import json
    metadata_size = len(json.dumps(metadata))
    max_size = getattr(settings, 'MAX_BACKUP_METADATA_SIZE', 64 * 1024)  # 64KB default
    
    if metadata_size > max_size:
        raise ValidationError(
            f"Backup metadata exceeds maximum size of {max_size} bytes"
        )
    
    return True


def validate_retention_policy(policy_config):
    """
    Validate retention policy configuration
    
    Args:
        policy_config (dict): Retention policy configuration
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If retention policy is invalid
    """
    if not isinstance(policy_config, dict):
        raise ValidationError("Retention policy must be a dictionary")
    
    policy_type = policy_config.get('type')
    if not policy_type:
        raise ValidationError("Retention policy must specify a type")
    
    valid_policy_types = ['daily', 'weekly', 'monthly', 'yearly', 'gfs', 'custom']
    if policy_type not in valid_policy_types:
        raise ValidationError(
            f"Invalid retention policy type. Valid options: {', '.join(valid_policy_types)}"
        )
    
    if policy_type == 'gfs':
        return _validate_gfs_policy(policy_config)
    elif policy_type == 'custom':
        return _validate_custom_policy(policy_config)
    else:
        return _validate_simple_policy(policy_config)


def _validate_gfs_policy(config):
    """Validate Grandfather-Father-Son retention policy"""
    required_fields = ['keep_weekly', 'keep_monthly', 'keep_yearly']
    for field in required_fields:
        if field not in config:
            raise ValidationError(f"GFS policy missing required field: {field}")
        
        value = config[field]
        if not isinstance(value, int) or value < 0:
            raise ValidationError(f"GFS {field} must be a non-negative integer")
    
    return True


def _validate_custom_policy(config):
    """Validate custom retention policy"""
    if 'rules' not in config:
        raise ValidationError("Custom policy must specify rules")
    
    rules = config['rules']
    if not isinstance(rules, list):
        raise ValidationError("Custom policy rules must be a list")
    
    if len(rules) == 0:
        raise ValidationError("Custom policy must have at least one rule")
    
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValidationError("Each custom policy rule must be a dictionary")
        
        if 'condition' not in rule or 'action' not in rule:
            raise ValidationError("Each custom policy rule must have condition and action")
    
    return True


def _validate_simple_policy(config):
    """Validate simple retention policy (daily, weekly, monthly, yearly)"""
    if 'keep_days' not in config:
        raise ValidationError("Simple policy must specify keep_days")
    
    keep_days = config['keep_days']
    if not isinstance(keep_days, int) or keep_days < 1:
        raise ValidationError("keep_days must be a positive integer")
    
    return True


def validate_backup_schedule_config(schedule_config):
    """
    Validate backup schedule configuration
    
    Args:
        schedule_config (dict): Schedule configuration
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If schedule configuration is invalid
    """
    if not isinstance(schedule_config, dict):
        raise ValidationError("Schedule configuration must be a dictionary")
    
    frequency = schedule_config.get('frequency')
    if not frequency:
        raise ValidationError("Schedule must specify frequency")
    
    validate_backup_frequency(frequency)
    
    if frequency == 'custom':
        cron_expr = schedule_config.get('cron_expression')
        if not cron_expr:
            raise ValidationError("Custom schedule must specify cron_expression")
        validate_backup_schedule(cron_expr)
    
    # Validate retry configuration if present
    if 'retry_on_failure' in schedule_config:
        retry_config = schedule_config['retry_on_failure']
        if not isinstance(retry_config, bool):
            raise ValidationError("retry_on_failure must be a boolean")
        
        if retry_config:
            if 'retry_count' not in schedule_config:
                raise ValidationError("retry_count must be specified when retry_on_failure is True")
            
            retry_count = schedule_config['retry_count']
            if not isinstance(retry_count, int) or retry_count < 1 or retry_count > 10:
                raise ValidationError("retry_count must be an integer between 1 and 10")
            
            if 'retry_delay_minutes' in schedule_config:
                retry_delay = schedule_config['retry_delay_minutes']
                if not isinstance(retry_delay, int) or retry_delay < 1 or retry_delay > 1440:
                    raise ValidationError("retry_delay_minutes must be between 1 and 1440")
    
    return True


def validate_encryption_key(key, algorithm='AES-256-GCM'):
    """
    Validate encryption key
    
    Args:
        key (str): Encryption key to validate
        algorithm (str): Encryption algorithm
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If encryption key is invalid
    """
    if not isinstance(key, str):
        raise ValidationError("Encryption key must be a string")
    
    validate_encryption_algorithm(algorithm)
    
    key_requirements = {
        'AES-256-GCM': 32,  # 256 bits
        'AES-256-CBC': 32,
        'ChaCha20-Poly1305': 32,
        'Fernet': 32  # Fernet uses 32-byte keys
    }
    
    required_length = key_requirements.get(algorithm)
    if required_length and len(key) != required_length:
        raise ValidationError(
            f"Encryption key for {algorithm} must be exactly {required_length} bytes"
        )
    
    return True


def validate_backup_verification_config(verification_config):
    """
    Validate backup verification configuration
    
    Args:
        verification_config (dict): Verification configuration
        
    Returns:
        bool: True if valid, raises ValidationError if invalid
        
    Raises:
        ValidationError: If verification configuration is invalid
    """
    if not isinstance(verification_config, dict):
        raise ValidationError("Verification configuration must be a dictionary")
    
    methods = verification_config.get('methods', [])
    if not isinstance(methods, list):
        raise ValidationError("Verification methods must be a list")
    
    valid_methods = ['hash', 'size', 'test_restore', 'full']
    for method in methods:
        if method not in valid_methods:
            raise ValidationError(
                f"Invalid verification method: {method}. "
                f"Valid options: {', '.join(valid_methods)}"
            )
    
    # Validate test restore configuration if present
    if 'test_restore' in verification_config:
        test_restore_config = verification_config['test_restore']
        if not isinstance(test_restore_config, dict):
            raise ValidationError("test_restore configuration must be a dictionary")
        
        if 'timeout_minutes' in test_restore_config:
            timeout = test_restore_config['timeout_minutes']
            if not isinstance(timeout, int) or timeout < 1 or timeout > 1440:
                raise ValidationError("test_restore timeout must be between 1 and 1440 minutes")
    
    return True
