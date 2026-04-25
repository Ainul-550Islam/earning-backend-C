"""
Data Validator

Data validation service for integration system
to ensure data integrity and security.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import json
import re
from ..constants import (
    IntegrationType, IntegrationStatus, IntegrationLogLevel,
    INTEGRATION_TYPES, INTEGRATION_STATUSES, INTEGRATION_LOG_LEVELS,
    VALIDATION_RULES, ERROR_CODES
)
from ..exceptions import (
    IntegrationError, ValidationError, DataValidationError
)

logger = logging.getLogger(__name__)


class DataValidator:
    """
    Data validation service for integration system.
    
    Provides comprehensive data validation for:
    - Configuration data
    - Integration metadata
    - API request/response data
    - File uploads and downloads
    - Security and compliance checks
    """
    
    def __init__(self):
        self.validation_rules = VALIDATION_RULES
        self.error_codes = ERROR_CODES
        self.validation_stats = {
            'total_validations': 0,
            'successful_validations': 0,
            'failed_validations': 0,
            'avg_validation_time_ms': 0.0
        }
    
    def validate_integration_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate integration configuration data.
        
        Args:
            config: Integration configuration dictionary
            
        Returns:
            Validation result with success status and details
        """
        try:
            start_time = datetime.now()
            
            # Basic structure validation
            if not isinstance(config, dict):
                return {
                    'success': False,
                    'error': 'Configuration must be a dictionary',
                    'error_code': 'INVALID_CONFIG_TYPE'
                }
            
            # Required fields validation
            required_fields = ['name', 'type', 'config', 'credentials']
            missing_fields = [field for field in required_fields if field not in config]
            
            if missing_fields:
                return {
                    'success': False,
                    'error': f'Missing required fields: {", ".join(missing_fields)}',
                    'error_code': 'MISSING_REQUIRED_FIELDS',
                    'missing_fields': missing_fields
                }
            
            # Integration type validation
            integration_type = config.get('type')
            if integration_type not in INTEGRATION_TYPES:
                return {
                    'success': False,
                    'error': f'Invalid integration type: {integration_type}',
                    'error_code': 'INVALID_INTEGRATION_TYPE',
                    'valid_types': INTEGRATION_TYPES
                }
            
            # Type-specific validation
            type_validation_result = self._validate_type_specific_config(config)
            if not type_validation_result['success']:
                return type_validation_result
            
            # Credentials validation
            credentials_validation_result = self._validate_credentials(config.get('credentials', {}))
            if not credentials_validation_result['success']:
                return credentials_validation_result
            
            # Security validation
            security_validation_result = self._validate_security_config(config.get('security', {}))
            if not security_validation_result['success']:
                return security_validation_result
            
            # Update validation stats
            self._update_validation_stats(start_time)
            
            return {
                'success': True,
                'message': 'Integration configuration is valid',
                'validated_fields': list(config.keys()),
                'validation_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error validating integration config: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'VALIDATION_ERROR'
            }
    
    def validate_api_request(self, request_data: Dict[str, Any], 
                           integration_type: IntegrationType) -> Dict[str, Any]:
        """
        Validate API request data for specific integration type.
        
        Args:
            request_data: API request data
            integration_type: Type of integration
            
        Returns:
            Validation result with success status and details
        """
        try:
            start_time = datetime.now()
            
            # Basic request structure validation
            if not isinstance(request_data, dict):
                return {
                    'success': False,
                    'error': 'Request data must be a dictionary',
                    'error_code': 'INVALID_REQUEST_TYPE'
                }
            
            # Type-specific request validation
            type_validation_result = self._validate_type_specific_request(request_data, integration_type)
            if not type_validation_result['success']:
                return type_validation_result
            
            # Security validation
            security_validation_result = self._validate_request_security(request_data)
            if not security_validation_result['success']:
                return security_validation_result
            
            # Data format validation
            format_validation_result = self._validate_request_format(request_data, integration_type)
            if not format_validation_result['success']:
                return format_validation_result
            
            # Update validation stats
            self._update_validation_stats(start_time)
            
            return {
                'success': True,
                'message': 'API request is valid',
                'validated_fields': list(request_data.keys()),
                'validation_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error validating API request: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'VALIDATION_ERROR'
            }
    
    def validate_api_response(self, response_data: Dict[str, Any], 
                           integration_type: IntegrationType) -> Dict[str, Any]:
        """
        Validate API response data for specific integration type.
        
        Args:
            response_data: API response data
            integration_type: Type of integration
            
        Returns:
            Validation result with success status and details
        """
        try:
            start_time = datetime.now()
            
            # Basic response structure validation
            if not isinstance(response_data, dict):
                return {
                    'success': False,
                    'error': 'Response data must be a dictionary',
                    'error_code': 'INVALID_RESPONSE_TYPE'
                }
            
            # Type-specific response validation
            type_validation_result = self._validate_type_specific_response(response_data, integration_type)
            if not type_validation_result['success']:
                return type_validation_result
            
            # Data integrity validation
            integrity_validation_result = self._validate_response_integrity(response_data)
            if not integrity_validation_result['success']:
                return integrity_validation_result
            
            # Update validation stats
            self._update_validation_stats(start_time)
            
            return {
                'success': True,
                'message': 'API response is valid',
                'validated_fields': list(response_data.keys()),
                'validation_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error validating API response: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'VALIDATION_ERROR'
            }
    
    def validate_file_upload(self, file_data: Dict[str, Any], 
                          integration_type: IntegrationType) -> Dict[str, Any]:
        """
        Validate file upload data for specific integration type.
        
        Args:
            file_data: File upload data
            integration_type: Type of integration
            
        Returns:
            Validation result with success status and details
        """
        try:
            start_time = datetime.now()
            
            # Basic file structure validation
            required_fields = ['filename', 'content_type', 'size', 'content']
            missing_fields = [field for field in required_fields if field not in file_data]
            
            if missing_fields:
                return {
                    'success': False,
                    'error': f'Missing required file fields: {", ".join(missing_fields)}',
                    'error_code': 'MISSING_FILE_FIELDS',
                    'missing_fields': missing_fields
                }
            
            # File size validation
            file_size = file_data.get('size', 0)
            max_size = self._get_max_file_size(integration_type)
            
            if file_size > max_size:
                return {
                    'success': False,
                    'error': f'File size {file_size} exceeds maximum {max_size}',
                    'error_code': 'FILE_SIZE_EXCEEDED',
                    'max_size': max_size
                }
            
            # File type validation
            content_type = file_data.get('content_type', '')
            allowed_types = self._get_allowed_file_types(integration_type)
            
            if content_type not in allowed_types:
                return {
                    'success': False,
                    'error': f'File type {content_type} is not allowed',
                    'error_code': 'INVALID_FILE_TYPE',
                    'allowed_types': allowed_types
                }
            
            # Security validation
            security_validation_result = self._validate_file_security(file_data)
            if not security_validation_result['success']:
                return security_validation_result
            
            # Update validation stats
            self._update_validation_stats(start_time)
            
            return {
                'success': True,
                'message': 'File upload is valid',
                'validated_fields': list(file_data.keys()),
                'validation_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error validating file upload: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'VALIDATION_ERROR'
            }
    
    def _validate_type_specific_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration specific to integration type."""
        try:
            integration_type = config.get('type')
            integration_config = config.get('config', {})
            
            if integration_type == IntegrationType.WEBHOOK:
                return self._validate_webhook_config(integration_config)
            elif integration_type == IntegrationType.API:
                return self._validate_api_config(integration_config)
            elif integration_type == IntegrationType.DATABASE:
                return self._validate_database_config(integration_config)
            elif integration_type == IntegrationType.MESSAGE_QUEUE:
                return self._validate_message_queue_config(integration_config)
            else:
                return {
                    'success': True,
                    'message': f'No specific validation for {integration_type}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_code': 'TYPE_VALIDATION_ERROR'
            }
    
    def _validate_webhook_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate webhook-specific configuration."""
        try:
            # Required webhook fields
            required_fields = ['url', 'secret', 'events']
            missing_fields = [field for field in required_fields if field not in config]
            
            if missing_fields:
                return {
                    'success': False,
                    'error': f'Missing webhook fields: {", ".join(missing_fields)}',
                    'error_code': 'MISSING_WEBHOOK_FIELDS',
                    'missing_fields': missing_fields
                }
            
            # URL validation
            url = config.get('url', '')
            if not self._is_valid_url(url):
                return {
                    'success': False,
                    'error': f'Invalid webhook URL: {url}',
                    'error_code': 'INVALID_WEBHOOK_URL'
                }
            
            # Secret validation
            secret = config.get('secret', '')
            if len(secret) < 16:
                return {
                    'success': False,
                    'error': 'Webhook secret must be at least 16 characters',
                    'error_code': 'INVALID_WEBHOOK_SECRET'
                }
            
            return {
                'success': True,
                'message': 'Webhook configuration is valid'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_code': 'WEBHOOK_CONFIG_ERROR'
            }
    
    def _validate_api_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate API-specific configuration."""
        try:
            # Required API fields
            required_fields = ['base_url', 'auth_type', 'timeout']
            missing_fields = [field for field in required_fields if field not in config]
            
            if missing_fields:
                return {
                    'success': False,
                    'error': f'Missing API fields: {", ".join(missing_fields)}',
                    'error_code': 'MISSING_API_FIELDS',
                    'missing_fields': missing_fields
                }
            
            # Base URL validation
            base_url = config.get('base_url', '')
            if not self._is_valid_url(base_url):
                return {
                    'success': False,
                    'error': f'Invalid API base URL: {base_url}',
                    'error_code': 'INVALID_API_URL'
                }
            
            # Timeout validation
            timeout = config.get('timeout', 30)
            if timeout <= 0 or timeout > 300:
                return {
                    'success': False,
                    'error': f'Invalid timeout value: {timeout}',
                    'error_code': 'INVALID_TIMEOUT'
                }
            
            return {
                'success': True,
                'message': 'API configuration is valid'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_code': 'API_CONFIG_ERROR'
            }
    
    def _validate_database_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate database-specific configuration."""
        try:
            # Required database fields
            required_fields = ['connection_string', 'database_type']
            missing_fields = [field for field in required_fields if field not in config]
            
            if missing_fields:
                return {
                    'success': False,
                    'error': f'Missing database fields: {", ".join(missing_fields)}',
                    'error_code': 'MISSING_DATABASE_FIELDS',
                    'missing_fields': missing_fields
                }
            
            # Database type validation
            db_type = config.get('database_type', '')
            valid_db_types = ['postgresql', 'mysql', 'sqlite', 'mongodb']
            
            if db_type not in valid_db_types:
                return {
                    'success': False,
                    'error': f'Invalid database type: {db_type}',
                    'error_code': 'INVALID_DATABASE_TYPE',
                    'valid_types': valid_db_types
                }
            
            return {
                'success': True,
                'message': 'Database configuration is valid'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_code': 'DATABASE_CONFIG_ERROR'
            }
    
    def _validate_message_queue_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate message queue-specific configuration."""
        try:
            # Required message queue fields
            required_fields = ['queue_name', 'connection_params', 'message_format']
            missing_fields = [field for field in required_fields if field not in config]
            
            if missing_fields:
                return {
                    'success': False,
                    'error': f'Missing message queue fields: {", ".join(missing_fields)}',
                    'error_code': 'MISSING_MQ_FIELDS',
                    'missing_fields': missing_fields
                }
            
            # Queue name validation
            queue_name = config.get('queue_name', '')
            if not re.match(r'^[a-zA-Z0-9_-]+$', queue_name):
                return {
                    'success': False,
                    'error': f'Invalid queue name: {queue_name}',
                    'error_code': 'INVALID_QUEUE_NAME'
                }
            
            return {
                'success': True,
                'message': 'Message queue configuration is valid'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_code': 'MQ_CONFIG_ERROR'
            }
    
    def _validate_credentials(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Validate integration credentials."""
        try:
            if not credentials:
                return {
                    'success': False,
                    'error': 'Credentials are required',
                    'error_code': 'MISSING_CREDENTIALS'
                }
            
            # Check for sensitive data exposure
            sensitive_fields = ['password', 'secret', 'token', 'key']
            for field in sensitive_fields:
                if field in credentials and len(str(credentials[field])) < 8:
                    return {
                        'success': False,
                        'error': f'{field} must be at least 8 characters',
                        'error_code': 'INVALID_CREDENTIAL_LENGTH'
                    }
            
            return {
                'success': True,
                'message': 'Credentials are valid'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_code': 'CREDENTIAL_VALIDATION_ERROR'
            }
    
    def _validate_security_config(self, security: Dict[str, Any]) -> Dict[str, Any]:
        """Validate security configuration."""
        try:
            # SSL/TLS validation
            if 'ssl_verify' in security:
                ssl_verify = security['ssl_verify']
                if not isinstance(ssl_verify, bool):
                    return {
                        'success': False,
                        'error': 'SSL verify must be a boolean',
                        'error_code': 'INVALID_SSL_VERIFY'
                    }
            
            # Rate limiting validation
            if 'rate_limit' in security:
                rate_limit = security['rate_limit']
                if not isinstance(rate_limit, int) or rate_limit <= 0:
                    return {
                        'success': False,
                        'error': 'Rate limit must be a positive integer',
                        'error_code': 'INVALID_RATE_LIMIT'
                    }
            
            return {
                'success': True,
                'message': 'Security configuration is valid'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_code': 'SECURITY_VALIDATION_ERROR'
            }
    
    def _validate_request_security(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate request security."""
        try:
            # Check for SQL injection patterns
            request_str = json.dumps(request_data)
            sql_patterns = [
                r'(?i)\b(union|select|insert|update|delete|drop|create|alter)\b',
                r'(?i)\b(exec|execute|sp|xp_cmdshell)\b'
            ]
            
            for pattern in sql_patterns:
                if re.search(pattern, request_str):
                    return {
                        'success': False,
                        'error': 'Potential SQL injection detected',
                        'error_code': 'SQL_INJECTION_DETECTED'
                    }
            
            # Check for XSS patterns
            xss_patterns = [
                r'<script[^>]*>.*?</script>',
                r'javascript:',
                r'on\w+\s*=',
                r'<iframe[^>]*>'
            ]
            
            for pattern in xss_patterns:
                if re.search(pattern, request_str):
                    return {
                        'success': False,
                        'error': 'Potential XSS detected',
                        'error_code': 'XSS_DETECTED'
                    }
            
            return {
                'success': True,
                'message': 'Request security validation passed'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_code': 'SECURITY_VALIDATION_ERROR'
            }
    
    def _validate_request_format(self, request_data: Dict[str, Any], 
                             integration_type: IntegrationType) -> Dict[str, Any]:
        """Validate request format for specific integration type."""
        try:
            if integration_type == IntegrationType.API:
                # API request format validation
                if 'headers' not in request_data:
                    return {
                        'success': False,
                        'error': 'API requests require headers',
                        'error_code': 'MISSING_API_HEADERS'
                    }
                
                if 'method' not in request_data:
                    return {
                        'success': False,
                        'error': 'API requests require HTTP method',
                        'error_code': 'MISSING_API_METHOD'
                    }
            
            return {
                'success': True,
                'message': 'Request format is valid'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_code': 'FORMAT_VALIDATION_ERROR'
            }
    
    def _validate_response_integrity(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate response data integrity."""
        try:
            # Check for required response fields
            if 'status' not in response_data:
                return {
                    'success': False,
                    'error': 'Response must include status field',
                    'error_code': 'MISSING_RESPONSE_STATUS'
                }
            
            # Check status code validity
            status = response_data.get('status')
            if isinstance(status, int) and (status < 100 or status > 599):
                return {
                    'success': False,
                    'error': f'Invalid HTTP status code: {status}',
                    'error_code': 'INVALID_STATUS_CODE'
                }
            
            return {
                'success': True,
                'message': 'Response integrity is valid'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_code': 'INTEGRITY_VALIDATION_ERROR'
            }
    
    def _validate_file_security(self, file_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate file security."""
        try:
            filename = file_data.get('filename', '')
            
            # Check for dangerous file extensions
            dangerous_extensions = ['.exe', '.bat', '.cmd', '.scr', '.pif', '.com']
            for ext in dangerous_extensions:
                if filename.lower().endswith(ext):
                    return {
                        'success': False,
                        'error': f'Dangerous file extension: {ext}',
                        'error_code': 'DANGEROUS_FILE_EXTENSION'
                    }
            
            # Check for path traversal
            if '..' in filename or '/' in filename:
                return {
                    'success': False,
                    'error': 'Path traversal detected in filename',
                    'error_code': 'PATH_TRAVERSAL_DETECTED'
                }
            
            return {
                'success': True,
                'message': 'File security validation passed'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_code': 'FILE_SECURITY_ERROR'
            }
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid."""
        try:
            import re
            url_pattern = re.compile(
                r'^https?://'  # http or https
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
                r'(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
                r'(?::\d+)?'  # port
                r'(?:/?|[/?]\S+)$',  # path
                re.IGNORECASE
            )
            return bool(url_pattern.match(url))
        except:
            return False
    
    def _get_max_file_size(self, integration_type: IntegrationType) -> int:
        """Get maximum file size for integration type."""
        size_limits = {
            IntegrationType.WEBHOOK: 10 * 1024 * 1024,  # 10MB
            IntegrationType.API: 50 * 1024 * 1024,     # 50MB
            IntegrationType.DATABASE: 100 * 1024 * 1024,  # 100MB
            IntegrationType.MESSAGE_QUEUE: 20 * 1024 * 1024,  # 20MB
        }
        return size_limits.get(integration_type, 10 * 1024 * 1024)
    
    def _get_allowed_file_types(self, integration_type: IntegrationType) -> List[str]:
        """Get allowed file types for integration type."""
        type_mappings = {
            IntegrationType.WEBHOOK: ['application/json', 'text/plain'],
            IntegrationType.API: ['application/json', 'application/xml', 'text/plain'],
            IntegrationType.DATABASE: ['application/sql', 'text/plain'],
            IntegrationType.MESSAGE_QUEUE: ['application/json', 'text/plain']
        }
        return type_mappings.get(integration_type, ['application/json'])
    
    def _update_validation_stats(self, start_time):
        """Update validation statistics."""
        try:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            self.validation_stats['total_validations'] += 1
            self.validation_stats['successful_validations'] += 1
            
            # Update average time
            current_avg = self.validation_stats['avg_validation_time_ms']
            total_validations = self.validation_stats['total_validations']
            self.validation_stats['avg_validation_time_ms'] = (
                (current_avg * (total_validations - 1) + execution_time) / total_validations
            )
            
        except Exception as e:
            logger.error(f"Error updating validation stats: {e}")
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        return self.validation_stats
    
    def reset_validation_stats(self) -> bool:
        """Reset validation statistics."""
        try:
            self.validation_stats = {
                'total_validations': 0,
                'successful_validations': 0,
                'failed_validations': 0,
                'avg_validation_time_ms': 0.0
            }
            
            logger.info("Reset validation statistics")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting validation stats: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on data validator."""
        try:
            # Test basic validation
            test_config = {
                'name': 'Test Integration',
                'type': IntegrationType.WEBHOOK,
                'config': {'url': 'https://example.com/webhook'},
                'credentials': {'secret': 'test_secret_1234567890123456'}
            }
            
            validation_result = self.validate_integration_config(test_config)
            
            return {
                'status': 'healthy' if validation_result['success'] else 'unhealthy',
                'validation_test': validation_result,
                'validation_stats': self.validation_stats,
                'supported_types': INTEGRATION_TYPES,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in data validator health check: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


# Global instance
data_validator = DataValidator()
