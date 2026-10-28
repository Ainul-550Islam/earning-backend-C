"""
Data Validator Module
Data validation system for integration
"""

import logging
import re
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.conf import settings
from django.core.exceptions import ValidationError

from ..models import SecurityLog, SecurityIncident
from ..utils import SecurityUtils
from .integ_constants import ValidationLevel

User = get_user_model()
logger = logging.getLogger('security.integration.validator')


class ValidationRule:
    """Base validation rule"""
    
    def __init__(self, name: str, field: str, level: ValidationLevel = ValidationLevel.BASIC):
        self.name = name
        self.field = field
        self.level = level
        self.enabled = True
        self.error_message = f"Validation failed for field: {field}"
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> bool:
        """Validate value - override in subclasses"""
        raise NotImplementedError("Subclasses must implement validate method")
    
    def get_error_message(self) -> str:
        """Get error message"""
        return self.error_message
    
    def enable(self):
        """Enable rule"""
        self.enabled = True
    
    def disable(self):
        """Disable rule"""
        self.enabled = False


class RequiredRule(ValidationRule):
    """Required field validation rule"""
    
    def __init__(self, field: str):
        super().__init__("required", field)
        self.error_message = f"Field {field} is required"
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> bool:
        return value is not None and value != ""


class TypeRule(ValidationRule):
    """Type validation rule"""
    
    def __init__(self, field: str, expected_type: Type):
        super().__init__("type", field)
        self.expected_type = expected_type
        self.error_message = f"Field {field} must be of type {expected_type.__name__}"
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> bool:
        return isinstance(value, self.expected_type)


class LengthRule(ValidationRule):
    """Length validation rule"""
    
    def __init__(self, field: str, min_length: int = None, max_length: int = None):
        super().__init__("length", field)
        self.min_length = min_length
        self.max_length = max_length
        
        if min_length and max_length:
            self.error_message = f"Field {field} must be between {min_length} and {max_length} characters"
        elif min_length:
            self.error_message = f"Field {field} must be at least {min_length} characters"
        elif max_length:
            self.error_message = f"Field {field} must be at most {max_length} characters"
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> bool:
        if value is None:
            return True
        
        length = len(str(value))
        
        if self.min_length and length < self.min_length:
            return False
        
        if self.max_length and length > self.max_length:
            return False
        
        return True


class RegexRule(ValidationRule):
    """Regex validation rule"""
    
    def __init__(self, field: str, pattern: str, flags: int = 0):
        super().__init__("regex", field)
        self.pattern = pattern
        self.regex = re.compile(pattern, flags)
        self.error_message = f"Field {field} does not match required pattern"
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> bool:
        if value is None:
            return True
        
        return bool(self.regex.match(str(value)))


class EmailRule(RegexRule):
    """Email validation rule"""
    
    def __init__(self, field: str):
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        super().__init__(field, pattern)
        self.error_message = f"Field {field} must be a valid email address"


class URLRule(RegexRule):
    """URL validation rule"""
    
    def __init__(self, field: str):
        pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        super().__init__(field, pattern)
        self.error_message = f"Field {field} must be a valid URL"


class NumericRule(ValidationRule):
    """Numeric validation rule"""
    
    def __init__(self, field: str, min_value: float = None, max_value: float = None):
        super().__init__("numeric", field)
        self.min_value = min_value
        self.max_value = max_value
        
        if min_value is not None and max_value is not None:
            self.error_message = f"Field {field} must be between {min_value} and {max_value}"
        elif min_value is not None:
            self.error_message = f"Field {field} must be at least {min_value}"
        elif max_value is not None:
            self.error_message = f"Field {field} must be at most {max_value}"
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> bool:
        if value is None:
            return True
        
        try:
            num_value = float(value)
            
            if self.min_value is not None and num_value < self.min_value:
                return False
            
            if self.max_value is not None and num_value > self.max_value:
                return False
            
            return True
        except ValueError:
            return False


class DateRule(ValidationRule):
    """Date validation rule"""
    
    def __init__(self, field: str, min_date: datetime = None, max_date: datetime = None):
        super().__init__("date", field)
        self.min_date = min_date
        self.max_date = max_date
        
        if min_date and max_date:
            self.error_message = f"Field {field} must be between {min_date} and {max_date}"
        elif min_date:
            self.error_message = f"Field {field} must be after {min_date}"
        elif max_date:
            self.error_message = f"Field {field} must be before {max_date}"
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> bool:
        if value is None:
            return True
        
        try:
            if isinstance(value, str):
                date_value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            elif isinstance(value, datetime):
                date_value = value
            else:
                return False
            
            if self.min_date and date_value < self.min_date:
                return False
            
            if self.max_date and date_value > self.max_date:
                return False
            
            return True
        except ValueError:
            return False


class ChoiceRule(ValidationRule):
    """Choice validation rule"""
    
    def __init__(self, field: str, choices: List[Any]):
        super().__init__("choice", field)
        self.choices = choices
        self.error_message = f"Field {field} must be one of: {choices}"
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> bool:
        return value in self.choices


class CustomRule(ValidationRule):
    """Custom validation rule"""
    
    def __init__(self, field: str, validator_func: Callable, error_message: str = None):
        super().__init__("custom", field)
        self.validator_func = validator_func
        self.error_message = error_message or f"Field {field} failed custom validation"
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> bool:
        return self.validator_func(value, context)


class IntegrationDataValidator:
    """Data validator for integration system"""
    
    def __init__(self, name: str):
        self.name = name
        self.rules = {}
        self.field_rules = {}
        self.global_rules = []
        self.validation_level = ValidationLevel.BASIC
        self.enabled = True
        self.statistics = {
            'validations': 0,
            'successes': 0,
            'failures': 0,
            'errors': 0
        }
    
    def add_rule(self, rule: ValidationRule):
        """Add validation rule"""
        if rule.field not in self.field_rules:
            self.field_rules[rule.field] = []
        
        self.field_rules[rule.field].append(rule)
        self.rules[rule.name] = rule
        
        logger.info(f"Added validation rule: {rule.name} for field: {rule.field}")
    
    def remove_rule(self, rule_name: str) -> bool:
        """Remove validation rule"""
        if rule_name in self.rules:
            rule = self.rules[rule_name]
            
            # Remove from field rules
            if rule.field in self.field_rules:
                self.field_rules[rule.field] = [
                    r for r in self.field_rules[rule.field] if r.name != rule_name
                ]
            
            del self.rules[rule_name]
            logger.info(f"Removed validation rule: {rule_name}")
            return True
        
        return False
    
    def add_global_rule(self, rule: ValidationRule):
        """Add global validation rule"""
        self.global_rules.append(rule)
        self.rules[rule.name] = rule
        logger.info(f"Added global validation rule: {rule.name}")
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate data"""
        if not self.enabled:
            return {
                'valid': True,
                'errors': [],
                'warnings': []
            }
        
        try:
            self.statistics['validations'] += 1
            
            errors = []
            warnings = []
            
            # Validate field-specific rules
            for field, rules in self.field_rules.items():
                value = data.get(field)
                
                for rule in rules:
                    if not rule.enabled:
                        continue
                    
                    # Check rule level
                    if not self._should_validate_rule(rule):
                        continue
                    
                    try:
                        if not rule.validate(value, context):
                            error_msg = rule.get_error_message()
                            
                            if rule.level == ValidationLevel.STRICT:
                                errors.append(error_msg)
                            else:
                                warnings.append(error_msg)
                    
                    except Exception as e:
                        logger.error(f"Error in validation rule {rule.name}: {e}")
                        errors.append(f"Validation error: {str(e)}")
            
            # Validate global rules
            for rule in self.global_rules:
                if not rule.enabled or not self._should_validate_rule(rule):
                    continue
                
                try:
                    if not rule.validate(data, context):
                        error_msg = rule.get_error_message()
                        
                        if rule.level == ValidationLevel.STRICT:
                            errors.append(error_msg)
                        else:
                            warnings.append(error_msg)
                
                except Exception as e:
                    logger.error(f"Error in global validation rule {rule.name}: {e}")
                    errors.append(f"Validation error: {str(e)}")
            
            # Update statistics
            if errors:
                self.statistics['failures'] += 1
            else:
                self.statistics['successes'] += 1
            
            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings,
                'validator': self.name
            }
        
        except Exception as e:
            self.statistics['errors'] += 1
            logger.error(f"Error in validator {self.name}: {e}")
            return {
                'valid': False,
                'errors': [f"Validation system error: {str(e)}"],
                'warnings': [],
                'validator': self.name
            }
    
    def _should_validate_rule(self, rule: ValidationRule) -> bool:
        """Check if rule should be validated based on validation level"""
        level_priority = {
            ValidationLevel.NONE: 0,
            ValidationLevel.BASIC: 1,
            ValidationLevel.STRICT: 2,
            ValidationLevel.CUSTOM: 3
        }
        
        rule_priority = level_priority.get(rule.level, 1)
        validator_priority = level_priority.get(self.validation_level, 1)
        
        return rule_priority <= validator_priority
    
    def set_validation_level(self, level: ValidationLevel):
        """Set validation level"""
        self.validation_level = level
        logger.info(f"Set validation level to: {level.value}")
    
    def enable(self):
        """Enable validator"""
        self.enabled = True
        logger.info(f"Validator {self.name} enabled")
    
    def disable(self):
        """Disable validator"""
        self.enabled = False
        logger.info(f"Validator {self.name} disabled")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get validator statistics"""
        total = self.statistics['validations']
        success_rate = (self.statistics['successes'] / total) if total > 0 else 0
        
        return {
            'name': self.name,
            'enabled': self.enabled,
            'validation_level': self.validation_level.value,
            'total_rules': len(self.rules),
            'field_rules_count': len(self.field_rules),
            'global_rules_count': len(self.global_rules),
            'statistics': {
                **self.statistics,
                'success_rate': success_rate
            }
        }


class ValidatorRegistry:
    """Registry for data validators"""
    
    def __init__(self):
        self.validators = {}
        self.validator_templates = {}
        self.enabled = True
    
    def register_validator(self, validator: IntegrationDataValidator):
        """Register validator"""
        self.validators[validator.name] = validator
        logger.info(f"Registered validator: {validator.name}")
    
    def unregister_validator(self, validator_name: str) -> bool:
        """Unregister validator"""
        if validator_name in self.validators:
            del self.validators[validator_name]
            logger.info(f"Unregistered validator: {validator_name}")
            return True
        return False
    
    def get_validator(self, validator_name: str) -> Optional[IntegrationDataValidator]:
        """Get validator by name"""
        return self.validators.get(validator_name)
    
    def create_validator(self, name: str, validation_level: ValidationLevel = ValidationLevel.BASIC) -> IntegrationDataValidator:
        """Create new validator"""
        validator = IntegrationDataValidator(name)
        validator.set_validation_level(validation_level)
        self.register_validator(validator)
        return validator
    
    def create_validator_from_template(self, template_name: str, validator_name: str, 
                                     overrides: Dict[str, Any] = None) -> Optional[IntegrationDataValidator]:
        """Create validator from template"""
        template = self.validator_templates.get(template_name)
        if not template:
            logger.error(f"Validator template not found: {template_name}")
            return None
        
        validator = IntegrationDataValidator(validator_name)
        validator.validation_level = template.get('validation_level', ValidationLevel.BASIC)
        
        # Add rules from template
        for rule_config in template.get('rules', []):
            rule = self._create_rule_from_config(rule_config)
            if rule:
                validator.add_rule(rule)
        
        # Apply overrides
        if overrides:
            if 'validation_level' in overrides:
                validator.set_validation_level(overrides['validation_level'])
        
        self.register_validator(validator)
        return validator
    
    def _create_rule_from_config(self, config: Dict[str, Any]) -> Optional[ValidationRule]:
        """Create rule from configuration"""
        rule_type = config.get('type')
        field = config.get('field')
        
        if not rule_type or not field:
            return None
        
        try:
            if rule_type == 'required':
                return RequiredRule(field)
            elif rule_type == 'email':
                return EmailRule(field)
            elif rule_type == 'url':
                return URLRule(field)
            elif rule_type == 'numeric':
                return NumericRule(field, config.get('min_value'), config.get('max_value'))
            elif rule_type == 'length':
                return LengthRule(field, config.get('min_length'), config.get('max_length'))
            elif rule_type == 'regex':
                return RegexRule(field, config.get('pattern'), config.get('flags', 0))
            elif rule_type == 'date':
                min_date = datetime.fromisoformat(config['min_date']) if config.get('min_date') else None
                max_date = datetime.fromisoformat(config['max_date']) if config.get('max_date') else None
                return DateRule(field, min_date, max_date)
            elif rule_type == 'choice':
                return ChoiceRule(field, config.get('choices', []))
            elif rule_type == 'custom':
                # Custom rules need to be handled separately
                return None
            
        except Exception as e:
            logger.error(f"Error creating rule from config: {e}")
        
        return None
    
    def register_validator_template(self, template_name: str, template_config: Dict[str, Any]):
        """Register validator template"""
        self.validator_templates[template_name] = template_config
        logger.info(f"Registered validator template: {template_name}")
    
    def validate_with_validator(self, validator_name: str, data: Dict[str, Any], 
                               context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate data with specific validator"""
        validator = self.get_validator(validator_name)
        if not validator:
            return {
                'valid': False,
                'errors': [f'Validator not found: {validator_name}'],
                'warnings': []
            }
        
        return validator.validate(data, context)
    
    def get_all_statistics(self) -> Dict[str, Any]:
        """Get statistics for all validators"""
        return {
            'enabled': self.enabled,
            'total_validators': len(self.validators),
            'total_templates': len(self.validator_templates),
            'validators': {
                name: validator.get_statistics()
                for name, validator in self.validators.items()
            }
        }
    
    def enable_all_validators(self):
        """Enable all validators"""
        for validator in self.validators.values():
            validator.enable()
    
    def disable_all_validators(self):
        """Disable all validators"""
        for validator in self.validators.values():
            validator.disable()
    
    def enable(self):
        """Enable validator registry"""
        self.enabled = True
        logger.info("Validator registry enabled")
    
    def disable(self):
        """Disable validator registry"""
        self.enabled = False
        logger.info("Validator registry disabled")


# Global validator registry
validator_registry = ValidatorRegistry()


# Create default validators and templates
def create_default_validators():
    """Create default validators"""
    
    # Security event validator
    security_validator = validator_registry.create_validator('security_event', ValidationLevel.STRICT)
    security_validator.add_rule(RequiredRule('event_type'))
    security_validator.add_rule(RequiredRule('timestamp'))
    security_validator.add_rule(ChoiceRule('severity', ['low', 'medium', 'high', 'critical']))
    security_validator.add_rule(EmailRule('user_email'))
    
    # User data validator
    user_validator = validator_registry.create_validator('user_data', ValidationLevel.BASIC)
    user_validator.add_rule(RequiredRule('username'))
    user_validator.add_rule(LengthRule('username', min_length=3, max_length=50))
    user_validator.add_rule(RegexRule('username', r'^[a-zA-Z0-9_]+$'))
    user_validator.add_rule(EmailRule('email'))
    
    # Threat data validator
    threat_validator = validator_registry.create_validator('threat_data', ValidationLevel.STRICT)
    threat_validator.add_rule(RequiredRule('threat_type'))
    threat_validator.add_rule(RequiredRule('indicator'))
    threat_validator.add_rule(ChoiceRule('severity', ['low', 'medium', 'high', 'critical']))
    threat_validator.add_rule(URLRule('source_url'))
    
    # API request validator
    api_validator = validator_registry.create_validator('api_request', ValidationLevel.BASIC)
    api_validator.add_rule(RequiredRule('endpoint'))
    api_validator.add_rule(ChoiceRule('method', ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']))
    api_validator.add_rule(NumericRule('timeout', min_value=1, max_value=300))
    
    logger.info("Created default validators")


def create_default_templates():
    """Create default validator templates"""
    
    # Basic user template
    user_template = {
        'validation_level': ValidationLevel.BASIC.value,
        'rules': [
            {'type': 'required', 'field': 'username'},
            {'type': 'length', 'field': 'username', 'min_length': 3, 'max_length': 50},
            {'type': 'required', 'field': 'email'},
            {'type': 'email', 'field': 'email'}
        ]
    }
    validator_registry.register_validator_template('basic_user', user_template)
    
    # Strict security template
    security_template = {
        'validation_level': ValidationLevel.STRICT.value,
        'rules': [
            {'type': 'required', 'field': 'event_type'},
            {'type': 'required', 'field': 'timestamp'},
            {'type': 'choice', 'field': 'severity', 'choices': ['low', 'medium', 'high', 'critical']},
            {'type': 'required', 'field': 'source_ip'},
            {'type': 'regex', 'field': 'source_ip', 'pattern': r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'}
        ]
    }
    validator_registry.register_validator_template('strict_security', security_template)
    
    # API template
    api_template = {
        'validation_level': ValidationLevel.BASIC.value,
        'rules': [
            {'type': 'required', 'field': 'endpoint'},
            {'type': 'choice', 'field': 'method', 'choices': ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']},
            {'type': 'url', 'field': 'endpoint'},
            {'type': 'numeric', 'field': 'timeout', 'min_value': 1, 'max_value': 300}
        ]
    }
    validator_registry.register_validator_template('api_request', api_template)
    
    logger.info("Created default validator templates")


# Initialize defaults
create_default_validators()
create_default_templates()


# Export symbols
__all__ = [
    'ValidationRule',
    'RequiredRule',
    'TypeRule',
    'LengthRule',
    'RegexRule',
    'EmailRule',
    'URLRule',
    'NumericRule',
    'DateRule',
    'ChoiceRule',
    'CustomRule',
    'IntegrationDataValidator',
    'ValidatorRegistry',
    'validator_registry',
    'create_default_validators',
    'create_default_templates'
]