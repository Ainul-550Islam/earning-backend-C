"""Data Validator

This module provides comprehensive data validation for integration system
with schema validation, business rules, and security checks.
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from abc import ABC, abstractmethod
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError

from .integ_constants import ValidationType, HealthStatus
from .integ_exceptions import ValidationError as IntegrationValidationError
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class BaseValidator(ABC):
    """
    Abstract base class for data validators.
    Defines the interface that all validators must implement.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the validator."""
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.monitor = PerformanceMonitor()
        
        # Load configuration
        self._load_configuration()
    
    def _load_configuration(self):
        """Load validator configuration."""
        try:
            self.enabled = self.config.get('enabled', True)
            self.strict_mode = self.config.get('strict_mode', False)
            self.cache_results = self.config.get('cache_results', True)
            self.cache_timeout = self.config.get('cache_timeout', 300)  # 5 minutes
            
        except Exception as e:
            self.logger.error(f"Error loading validator configuration: {str(e)}")
            self.enabled = True
            self.strict_mode = False
            self.cache_results = True
            self.cache_timeout = 300
    
    @abstractmethod
    def validate(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate data according to validator rules.
        
        Args:
            data: Data to validate
            context: Additional context
            
        Returns:
            Validation result
        """
        pass
    
    @abstractmethod
    def get_validator_info(self) -> Dict[str, Any]:
        """
        Get validator information.
        
        Returns:
            Validator information
        """
        pass
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of validator.
        
        Returns:
            Health check results
        """
        try:
            return {
                'status': HealthStatus.HEALTHY,
                'enabled': self.enabled,
                'strict_mode': self.strict_mode,
                'cache_results': self.cache_results,
                'cache_timeout': self.cache_timeout,
                'checked_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'status': HealthStatus.UNHEALTHY,
                'error': str(e),
                'checked_at': timezone.now().isoformat()
            }


class SchemaValidator(BaseValidator):
    """
    Schema validator for JSON schema validation.
    Handles JSON schema validation with comprehensive error reporting.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the schema validator."""
        super().__init__(config)
        self.schemas = {}
        self._load_schemas()
    
    def _load_schemas(self):
        """Load validation schemas."""
        try:
            schema_definitions = self.config.get('schemas', {})
            
            for schema_name, schema_def in schema_definitions.items():
                self.schemas[schema_name] = schema_def
            
            self.logger.info(f"Loaded {len(self.schemas)} validation schemas")
            
        except Exception as e:
            self.logger.error(f"Error loading schemas: {str(e)}")
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate data against JSON schema.
        
        Args:
            data: Data to validate
            context: Additional context
            
        Returns:
            Validation result
        """
        try:
            with self.monitor.measure_validation('schema') as measurement:
                result = {
                    'valid': True,
                    'errors': [],
                    'warnings': [],
                    'schema': None,
                    'validated_at': timezone.now().isoformat()
                }
                
                # Get schema from context
                schema_name = context.get('schema_name') if context else None
                if not schema_name:
                    result['warnings'].append('No schema specified')
                    return result
                
                # Get schema
                schema = self.schemas.get(schema_name)
                if not schema:
                    result['valid'] = False
                    result['errors'].append(f'Schema not found: {schema_name}')
                    return result
                
                result['schema'] = schema_name
                
                # Validate against schema
                validation_result = self._validate_against_schema(data, schema)
                
                result['valid'] = validation_result['valid']
                result['errors'] = validation_result['errors']
                result['warnings'] = validation_result['warnings']
                
                return result
                
        except Exception as e:
            self.logger.error(f"Error in schema validation: {str(e)}")
            return {
                'valid': False,
                'errors': [str(e)],
                'warnings': [],
                'schema': None,
                'validated_at': timezone.now().isoformat()
            }
    
    def _validate_against_schema(self, data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data against specific schema."""
        try:
            # Use jsonschema for validation
            import jsonschema
            
            result = {
                'valid': True,
                'errors': [],
                'warnings': []
            }
            
            try:
                jsonschema.validate(data, schema)
            except jsonschema.ValidationError as e:
                result['valid'] = False
                result['errors'].append(f"Schema validation failed: {e.message}")
            except jsonschema.SchemaError as e:
                result['valid'] = False
                result['errors'].append(f"Schema error: {e.message}")
            
            return result
            
        except ImportError:
            # Fallback validation if jsonschema not available
            return self._basic_schema_validation(data, schema)
        except Exception as e:
            self.logger.error(f"Error in schema validation: {str(e)}")
            return {
                'valid': False,
                'errors': [str(e)],
                'warnings': []
            }
    
    def _basic_schema_validation(self, data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Basic schema validation without jsonschema."""
        try:
            result = {
                'valid': True,
                'errors': [],
                'warnings': []
            }
            
            # Check required fields
            required_fields = schema.get('required', [])
            for field in required_fields:
                if field not in data:
                    result['valid'] = False
                    result['errors'].append(f"Required field missing: {field}")
            
            # Check field types
            properties = schema.get('properties', {})
            for field, field_schema in properties.items():
                if field in data:
                    expected_type = field_schema.get('type')
                    if expected_type == 'string' and not isinstance(data[field], str):
                        result['valid'] = False
                        result['errors'].append(f"Field {field} must be string")
                    elif expected_type == 'number' and not isinstance(data[field], (int, float)):
                        result['valid'] = False
                        result['errors'].append(f"Field {field} must be number")
                    elif expected_type == 'boolean' and not isinstance(data[field], bool):
                        result['valid'] = False
                        result['errors'].append(f"Field {field} must be boolean")
                    elif expected_type == 'array' and not isinstance(data[field], list):
                        result['valid'] = False
                        result['errors'].append(f"Field {field} must be array")
                    elif expected_type == 'object' and not isinstance(data[field], dict):
                        result['valid'] = False
                        result['errors'].append(f"Field {field} must be object")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in basic schema validation: {str(e)}")
            return {
                'valid': False,
                'errors': [str(e)],
                'warnings': []
            }
    
    def get_validator_info(self) -> Dict[str, Any]:
        """
        Get schema validator information.
        
        Returns:
            Validator information
        """
        return {
            'type': ValidationType.SCHEMA,
            'name': 'SchemaValidator',
            'description': 'Validator for JSON schema validation',
            'version': '1.0.0',
            'schemas_count': len(self.schemas),
            'supported_schemas': list(self.schemas.keys()),
            'enabled': self.enabled,
            'config': self.config
        }


class BusinessValidator(BaseValidator):
    """
    Business validator for business rule validation.
    Handles custom business logic validation.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the business validator."""
        super().__init__(config)
        self.rules = {}
        self._load_rules()
    
    def _load_rules(self):
        """Load business validation rules."""
        try:
            rule_definitions = self.config.get('rules', {})
            
            for rule_name, rule_def in rule_definitions.items():
                self.rules[rule_name] = rule_def
            
            self.logger.info(f"Loaded {len(self.rules)} business validation rules")
            
        except Exception as e:
            self.logger.error(f"Error loading business rules: {str(e)}")
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate data against business rules.
        
        Args:
            data: Data to validate
            context: Additional context
            
        Returns:
            Validation result
        """
        try:
            with self.monitor.measure_validation('business') as measurement:
                result = {
                    'valid': True,
                    'errors': [],
                    'warnings': [],
                    'rules_applied': [],
                    'validated_at': timezone.now().isoformat()
                }
                
                # Get rules to apply
                rules_to_apply = self._get_rules_to_apply(context)
                
                # Apply each rule
                for rule_name in rules_to_apply:
                    rule = self.rules[rule_name]
                    rule_result = self._apply_rule(rule_name, rule, data, context)
                    
                    result['rules_applied'].append(rule_name)
                    result['valid'] = result['valid'] and rule_result['valid']
                    result['errors'].extend(rule_result['errors'])
                    result['warnings'].extend(rule_result['warnings'])
                
                return result
                
        except Exception as e:
            self.logger.error(f"Error in business validation: {str(e)}")
            return {
                'valid': False,
                'errors': [str(e)],
                'warnings': [],
                'rules_applied': [],
                'validated_at': timezone.now().isoformat()
            }
    
    def _get_rules_to_apply(self, context: Dict[str, Any] = None) -> List[str]:
        """Get rules to apply based on context."""
        try:
            if not context:
                return list(self.rules.keys())
            
            # Filter rules based on context
            applicable_rules = []
            
            for rule_name, rule in self.rules.items():
                rule_context = rule.get('context', {})
                
                # Check if rule applies to context
                if self._rule_applies_to_context(rule_context, context):
                    applicable_rules.append(rule_name)
            
            return applicable_rules
            
        except Exception as e:
            self.logger.error(f"Error getting rules to apply: {str(e)}")
            return list(self.rules.keys())
    
    def _rule_applies_to_context(self, rule_context: Dict[str, Any], data_context: Dict[str, Any]) -> bool:
        """Check if rule applies to given context."""
        try:
            # If no context specified, rule applies to all
            if not rule_context:
                return True
            
            # Check context conditions
            for key, value in rule_context.items():
                if key not in data_context or data_context[key] != value:
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking rule context: {str(e)}")
            return False
    
    def _apply_rule(self, rule_name: str, rule: Dict[str, Any], data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Apply a specific business rule."""
        try:
            result = {
                'valid': True,
                'errors': [],
                'warnings': []
            }
            
            rule_type = rule.get('type')
            
            if rule_type == 'field_comparison':
                result = self._apply_field_comparison_rule(rule, data)
            elif rule_type == 'value_range':
                result = self._apply_value_range_rule(rule, data)
            elif rule_type == 'conditional':
                result = self._apply_conditional_rule(rule, data)
            elif rule_type == 'custom':
                result = self._apply_custom_rule(rule_name, rule, data, context)
            else:
                result['warnings'].append(f"Unknown rule type: {rule_type}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error applying rule {rule_name}: {str(e)}")
            return {
                'valid': False,
                'errors': [str(e)],
                'warnings': []
            }
    
    def _apply_field_comparison_rule(self, rule: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply field comparison rule."""
        try:
            result = {
                'valid': True,
                'errors': [],
                'warnings': []
            }
            
            field1 = rule.get('field1')
            field2 = rule.get('field2')
            operator = rule.get('operator', 'equals')
            
            if field1 not in data or field2 not in data:
                result['valid'] = False
                result['errors'].append(f"Required fields missing: {field1}, {field2}")
                return result
            
            value1 = data[field1]
            value2 = data[field2]
            
            if operator == 'equals' and value1 != value2:
                result['valid'] = False
                result['errors'].append(f"Fields {field1} and {field2} must be equal")
            elif operator == 'not_equals' and value1 == value2:
                result['valid'] = False
                result['errors'].append(f"Fields {field1} and {field2} must not be equal")
            elif operator == 'greater_than' and not (value1 > value2):
                result['valid'] = False
                result['errors'].append(f"Field {field1} must be greater than {field2}")
            elif operator == 'less_than' and not (value1 < value2):
                result['valid'] = False
                result['errors'].append(f"Field {field1} must be less than {field2}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error applying field comparison rule: {str(e)}")
            return {
                'valid': False,
                'errors': [str(e)],
                'warnings': []
            }
    
    def _apply_value_range_rule(self, rule: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply value range rule."""
        try:
            result = {
                'valid': True,
                'errors': [],
                'warnings': []
            }
            
            field = rule.get('field')
            min_value = rule.get('min_value')
            max_value = rule.get('max_value')
            
            if field not in data:
                result['valid'] = False
                result['errors'].append(f"Required field missing: {field}")
                return result
            
            value = data[field]
            
            if min_value is not None and value < min_value:
                result['valid'] = False
                result['errors'].append(f"Field {field} must be at least {min_value}")
            
            if max_value is not None and value > max_value:
                result['valid'] = False
                result['errors'].append(f"Field {field} must be at most {max_value}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error applying value range rule: {str(e)}")
            return {
                'valid': False,
                'errors': [str(e)],
                'warnings': []
            }
    
    def _apply_conditional_rule(self, rule: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply conditional rule."""
        try:
            result = {
                'valid': True,
                'errors': [],
                'warnings': []
            }
            
            conditions = rule.get('conditions', [])
            
            for condition in conditions:
                field = condition.get('field')
                operator = condition.get('operator')
                expected_value = condition.get('value')
                
                if field not in data:
                    result['valid'] = False
                    result['errors'].append(f"Required field missing: {field}")
                    continue
                
                actual_value = data[field]
                
                condition_met = False
                if operator == 'equals':
                    condition_met = actual_value == expected_value
                elif operator == 'not_equals':
                    condition_met = actual_value != expected_value
                elif operator == 'contains':
                    condition_met = expected_value in str(actual_value)
                elif operator == 'not_contains':
                    condition_met = expected_value not in str(actual_value)
                
                if not condition_met:
                    result['valid'] = False
                    result['errors'].append(f"Condition not met: {field} {operator} {expected_value}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error applying conditional rule: {str(e)}")
            return {
                'valid': False,
                'errors': [str(e)],
                'warnings': []
            }
    
    def _apply_custom_rule(self, rule_name: str, rule: Dict[str, Any], data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Apply custom rule."""
        try:
            function_path = rule.get('function')
            if not function_path:
                return {
                    'valid': True,
                    'errors': [],
                    'warnings': ['No custom function specified']
                }
            
            # Import and execute custom function
            module_path, function_name = function_path.rsplit('.', 1)
            module = __import__(module_path, fromlist=[function_name])
            custom_function = getattr(module, function_name)
            
            return custom_function(data, context)
            
        except Exception as e:
            self.logger.error(f"Error applying custom rule {rule_name}: {str(e)}")
            return {
                'valid': False,
                'errors': [str(e)],
                'warnings': []
            }
    
    def get_validator_info(self) -> Dict[str, Any]:
        """
        Get business validator information.
        
        Returns:
            Validator information
        """
        return {
            'type': ValidationType.BUSINESS,
            'name': 'BusinessValidator',
            'description': 'Validator for business rule validation',
            'version': '1.0.0',
            'rules_count': len(self.rules),
            'supported_rules': list(self.rules.keys()),
            'enabled': self.enabled,
            'config': self.config
        }


class SecurityValidator(BaseValidator):
    """
    Security validator for security checks.
    Handles security validation like SQL injection, XSS, etc.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the security validator."""
        super().__init__(config)
        self.security_checks = {}
        self._load_security_checks()
    
    def _load_security_checks(self):
        """Load security validation checks."""
        try:
            check_definitions = self.config.get('security_checks', {})
            
            for check_name, check_def in check_definitions.items():
                self.security_checks[check_name] = check_def
            
            self.logger.info(f"Loaded {len(self.security_checks)} security checks")
            
        except Exception as e:
            self.logger.error(f"Error loading security checks: {str(e)}")
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate data for security issues.
        
        Args:
            data: Data to validate
            context: Additional context
            
        Returns:
            Validation result
        """
        try:
            with self.monitor.measure_validation('security') as measurement:
                result = {
                    'valid': True,
                    'errors': [],
                    'warnings': [],
                    'security_issues': [],
                    'checks_applied': [],
                    'validated_at': timezone.now().isoformat()
                }
                
                # Apply security checks
                for check_name, check in self.security_checks.items():
                    if check.get('enabled', True):
                        check_result = self._apply_security_check(check_name, check, data)
                        
                        result['checks_applied'].append(check_name)
                        result['valid'] = result['valid'] and check_result['valid']
                        result['errors'].extend(check_result['errors'])
                        result['warnings'].extend(check_result['warnings'])
                        result['security_issues'].extend(check_result['security_issues'])
                
                return result
                
        except Exception as e:
            self.logger.error(f"Error in security validation: {str(e)}")
            return {
                'valid': False,
                'errors': [str(e)],
                'warnings': [],
                'security_issues': [],
                'checks_applied': [],
                'validated_at': timezone.now().isoformat()
            }
    
    def _apply_security_check(self, check_name: str, check: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a specific security check."""
        try:
            result = {
                'valid': True,
                'errors': [],
                'warnings': [],
                'security_issues': []
            }
            
            check_type = check.get('type')
            
            if check_type == 'sql_injection':
                result = self._check_sql_injection(data)
            elif check_type == 'xss':
                result = self._check_xss(data)
            elif check_type == 'field_sanitization':
                result = self._check_field_sanitization(data, check.get('fields', []))
            elif check_type == 'custom':
                result = self._apply_custom_security_check(check_name, check, data)
            else:
                result['warnings'].append(f"Unknown security check type: {check_type}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error applying security check {check_name}: {str(e)}")
            return {
                'valid': False,
                'errors': [str(e)],
                'warnings': [],
                'security_issues': []
            }
    
    def _check_sql_injection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check for SQL injection patterns."""
        try:
            result = {
                'valid': True,
                'errors': [],
                'warnings': [],
                'security_issues': []
            }
            
            # SQL injection patterns
            sql_patterns = [
                r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b)',
                r'(\b(UNION|JOIN|WHERE|HAVING|GROUP BY|ORDER BY)\b)',
                r'(\b(OR|AND)\s+\d+\s*=\s*\d+)',
                r'(\'|\")\s*(OR|AND)\s*\1\s*=\s*\1',
                r'(--|#|\/\*|\*\/)',
                r'(\b(EXEC|EXECUTE|SP_|XP_)\b)',
                r'(\b(INFORMATION_SCHEMA|SYS|MASTER|MSDB)\b)'
            ]
            
            import re
            
            def check_value(value):
                """Check a single value for SQL injection."""
                if not isinstance(value, str):
                    return False
                
                for pattern in sql_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        return True
                
                return False
            
            # Check all string values
            for key, value in data.items():
                if check_value(value):
                    result['valid'] = False
                    result['security_issues'].append(f"Potential SQL injection in field: {key}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error checking SQL injection: {str(e)}")
            return {
                'valid': False,
                'errors': [str(e)],
                'warnings': [],
                'security_issues': []
            }
    
    def _check_xss(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check for XSS patterns."""
        try:
            result = {
                'valid': True,
                'errors': [],
                'warnings': [],
                'security_issues': []
            }
            
            # XSS patterns
            xss_patterns = [
                r'<script[^>]*>.*?</script>',
                r'<iframe[^>]*>.*?</iframe>',
                r'<object[^>]*>.*?</object>',
                r'<embed[^>]*>',
                r'<form[^>]*>',
                r'<input[^>]*>',
                r'<link[^>]*>',
                r'<meta[^>]*>',
                r'on\w+\s*=\s*["\'][^"\']*["\']',
                r'javascript:',
                r'vbscript:',
                r'data:text/html',
                r'expression\s*\(',
                r'@import',
                r'binding:'
            ]
            
            import re
            
            def check_value(value):
                """Check a single value for XSS."""
                if not isinstance(value, str):
                    return False
                
                for pattern in xss_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        return True
                
                return False
            
            # Check all string values
            for key, value in data.items():
                if check_value(value):
                    result['valid'] = False
                    result['security_issues'].append(f"Potential XSS in field: {key}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error checking XSS: {str(e)}")
            return {
                'valid': False,
                'errors': [str(e)],
                'warnings': [],
                'security_issues': []
            }
    
    def _check_field_sanitization(self, data: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        """Check field sanitization."""
        try:
            result = {
                'valid': True,
                'errors': [],
                'warnings': [],
                'security_issues': []
            }
            
            for field in fields:
                if field in data:
                    value = data[field]
                    
                    if isinstance(value, str):
                        # Check for dangerous characters
                        dangerous_chars = ['<', '>', '"', "'", '&', '\x00', '\n', '\r', '\t']
                        
                        for char in dangerous_chars:
                            if char in value:
                                result['valid'] = False
                                result['security_issues'].append(f"Field {field} contains dangerous character: {repr(char)}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error checking field sanitization: {str(e)}")
            return {
                'valid': False,
                'errors': [str(e)],
                'warnings': [],
                'security_issues': []
            }
    
    def _apply_custom_security_check(self, check_name: str, check: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply custom security check."""
        try:
            function_path = check.get('function')
            if not function_path:
                return {
                    'valid': True,
                    'errors': [],
                    'warnings': ['No custom function specified'],
                    'security_issues': []
                }
            
            # Import and execute custom function
            module_path, function_name = function_path.rsplit('.', 1)
            module = __import__(module_path, fromlist=[function_name])
            custom_function = getattr(module, function_name)
            
            return custom_function(data)
            
        except Exception as e:
            self.logger.error(f"Error applying custom security check {check_name}: {str(e)}")
            return {
                'valid': False,
                'errors': [str(e)],
                'warnings': [],
                'security_issues': []
            }
    
    def get_validator_info(self) -> Dict[str, Any]:
        """
        Get security validator information.
        
        Returns:
            Validator information
        """
        return {
            'type': ValidationType.SECURITY,
            'name': 'SecurityValidator',
            'description': 'Validator for security checks',
            'version': '1.0.0',
            'security_checks_count': len(self.security_checks),
            'supported_checks': list(self.security_checks.keys()),
            'enabled': self.enabled,
            'config': self.config
        }


class DataValidator:
    """
    Main data validator for integration system.
    Coordinates multiple validators and provides unified interface.
    """
    
    def __init__(self):
        """Initialize the data validator."""
        self.logger = logger
        self.validators = {}
        self.monitor = PerformanceMonitor()
        
        # Load configuration
        self._load_configuration()
        
        # Initialize validators
        self._initialize_validators()
    
    def _load_configuration(self):
        """Load validator configuration from settings."""
        try:
            self.config = getattr(settings, 'WEBHOOK_DATA_VALIDATOR_CONFIG', {})
            self.enabled_validators = self.config.get('enabled_validators', ['schema', 'business', 'security'])
            
            self.logger.info("Data validator configuration loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading data validator configuration: {str(e)}")
            self.config = {}
            self.enabled_validators = ['schema', 'business', 'security']
    
    def _initialize_validators(self):
        """Initialize enabled validators."""
        try:
            # Initialize schema validator
            if 'schema' in self.enabled_validators:
                schema_config = self.config.get('schema', {})
                self.validators['schema'] = SchemaValidator(schema_config)
            
            # Initialize business validator
            if 'business' in self.enabled_validators:
                business_config = self.config.get('business', {})
                self.validators['business'] = BusinessValidator(business_config)
            
            # Initialize security validator
            if 'security' in self.enabled_validators:
                security_config = self.config.get('security', {})
                self.validators['security'] = SecurityValidator(security_config)
            
            self.logger.info(f"Initialized {len(self.validators)} validators")
            
        except Exception as e:
            self.logger.error(f"Error initializing validators: {str(e)}")
    
    def validate_event_data(self, event_type: str, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate event data.
        
        Args:
            event_type: Event type
            data: Event data
            context: Additional context
            
        Returns:
            Validation result
        """
        try:
            with self.monitor.measure_validation('event') as measurement:
                result = {
                    'event_type': event_type,
                    'valid': True,
                    'errors': [],
                    'warnings': [],
                    'validator_results': {},
                    'validated_at': timezone.now().isoformat()
                }
                
                # Prepare context
                if not context:
                    context = {}
                context['event_type'] = event_type
                
                # Apply validators
                for validator_name, validator in self.validators.items():
                    try:
                        validator_result = validator.validate(data, context)
                        
                        result['validator_results'][validator_name] = validator_result
                        result['valid'] = result['valid'] and validator_result['valid']
                        result['errors'].extend(validator_result['errors'])
                        result['warnings'].extend(validator_result['warnings'])
                        
                    except Exception as e:
                        self.logger.error(f"Error in validator {validator_name}: {str(e)}")
                        result['validator_results'][validator_name] = {
                            'valid': False,
                            'errors': [str(e)],
                            'warnings': []
                        }
                        result['valid'] = False
                        result['errors'].append(f"Validator {validator_name} failed: {str(e)}")
                
                return result
                
        except Exception as e:
            self.logger.error(f"Error validating event data: {str(e)}")
            return {
                'event_type': event_type,
                'valid': False,
                'errors': [str(e)],
                'warnings': [],
                'validator_results': {},
                'validated_at': timezone.now().isoformat()
            }
    
    def validate_data(self, data: Dict[str, Any], validator_type: str = None, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate data using specified validator or all validators.
        
        Args:
            data: Data to validate
            validator_type: Optional specific validator type
            context: Additional context
            
        Returns:
            Validation result
        """
        try:
            with self.monitor.measure_validation('data') as measurement:
                result = {
                    'valid': True,
                    'errors': [],
                    'warnings': [],
                    'validator_results': {},
                    'validated_at': timezone.now().isoformat()
                }
                
                # Apply specific validator or all validators
                if validator_type:
                    if validator_type in self.validators:
                        validator = self.validators[validator_type]
                        validator_result = validator.validate(data, context)
                        
                        result['validator_results'][validator_type] = validator_result
                        result['valid'] = validator_result['valid']
                        result['errors'] = validator_result['errors']
                        result['warnings'] = validator_result['warnings']
                    else:
                        result['valid'] = False
                        result['errors'].append(f'Validator not found: {validator_type}')
                else:
                    # Apply all validators
                    for validator_name, validator in self.validators.items():
                        try:
                            validator_result = validator.validate(data, context)
                            
                            result['validator_results'][validator_name] = validator_result
                            result['valid'] = result['valid'] and validator_result['valid']
                            result['errors'].extend(validator_result['errors'])
                            result['warnings'].extend(validator_result['warnings'])
                            
                        except Exception as e:
                            self.logger.error(f"Error in validator {validator_name}: {str(e)}")
                            result['validator_results'][validator_name] = {
                                'valid': False,
                                'errors': [str(e)],
                                'warnings': []
                            }
                            result['valid'] = False
                            result['errors'].append(f"Validator {validator_name} failed: {str(e)}")
                
                return result
                
        except Exception as e:
            self.logger.error(f"Error validating data: {str(e)}")
            return {
                'valid': False,
                'errors': [str(e)],
                'warnings': [],
                'validator_results': {},
                'validated_at': timezone.now().isoformat()
            }
    
    def get_validator_status(self, validator_type: str = None) -> Dict[str, Any]:
        """
        Get validator status.
        
        Args:
            validator_type: Optional specific validator type
            
        Returns:
            Validator status information
        """
        try:
            if validator_type:
                if validator_type in self.validators:
                    return self.validators[validator_type].health_check()
                else:
                    return {'error': f'Validator {validator_type} not found'}
            else:
                return {
                    'total_validators': len(self.validators),
                    'enabled_validators': self.enabled_validators,
                    'validators': {
                        name: validator.health_check()
                        for name, validator in self.validators.items()
                    }
                }
                
        except Exception as e:
            self.logger.error(f"Error getting validator status: {str(e)}")
            return {'error': str(e)}
    
    def register_validator(self, validator_type: str, validator: BaseValidator) -> bool:
        """
        Register a custom validator.
        
        Args:
            validator_type: Type of validator
            validator: Validator instance
            
        Returns:
            True if registration successful
        """
        try:
            if not isinstance(validator, BaseValidator):
                raise IntegrationValidationError("Validator must inherit from BaseValidator")
            
            self.validators[validator_type] = validator
            self.logger.info(f"Validator {validator_type} registered successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error registering validator {validator_type}: {str(e)}")
            return False
    
    def unregister_validator(self, validator_type: str) -> bool:
        """
        Unregister a validator.
        
        Args:
            validator_type: Type of validator to unregister
            
        Returns:
            True if unregistration successful
        """
        try:
            if validator_type in self.validators:
                del self.validators[validator_type]
                self.logger.info(f"Validator {validator_type} unregistered successfully")
                return True
            else:
                self.logger.warning(f"Validator {validator_type} not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Error unregistering validator {validator_type}: {str(e)}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of validator system.
        
        Returns:
            Health check results
        """
        try:
            health_status = {
                'overall': HealthStatus.HEALTHY,
                'components': {},
                'checks': []
            }
            
            # Check validators
            for validator_type, validator in self.validators.items():
                validator_health = validator.health_check()
                health_status['components'][validator_type] = validator_health
                
                if validator_health['status'] != HealthStatus.HEALTHY:
                    health_status['overall'] = HealthStatus.UNHEALTHY
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'overall': HealthStatus.UNHEALTHY,
                'error': str(e)
            }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get validator system status.
        
        Returns:
            System status
        """
        try:
            return {
                'data_validator': {
                    'status': 'running',
                    'total_validators': len(self.validators),
                    'enabled_validators': self.enabled_validators,
                    'uptime': self.monitor.get_uptime(),
                    'performance_metrics': self.monitor.get_system_metrics()
                },
                'validators': {
                    name: validator.get_validator_info()
                    for name, validator in self.validators.items()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting validator status: {str(e)}")
            return {'error': str(e)}
