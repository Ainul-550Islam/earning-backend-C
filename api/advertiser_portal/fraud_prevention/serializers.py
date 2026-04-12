"""
Fraud Prevention Serializers

This module provides comprehensive serializers for fraud prevention operations with
enterprise-grade validation, security, and performance optimization following
industry standards from Stripe, OgAds, and leading fraud prevention systems.
"""

from typing import Optional, List, Dict, Any, Union, Tuple
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID
import json

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Sum, Count, Avg, Q, F
from django.db.models.functions import Coalesce

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.creative_model import Creative
from ..database_models.fraud_model import FraudDetection, RiskScore, FraudPattern, SecurityAlert
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class FraudDetectionSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for FraudDetection model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    user_id_str = serializers.CharField(source='user_id', read_only=True)
    detected_patterns_list = serializers.ListField(source='detected_patterns', read_only=True)
    risk_factors_dict = serializers.DictField(source='risk_factors', read_only=True)
    recommended_actions_list = serializers.ListField(source='recommended_actions', read_only=True)
    
    class Meta:
        model = FraudDetection
        fields = [
            'id', 'user_id', 'user_id_str', 'session_id', 'event_type',
            'risk_score', 'is_fraudulent', 'confidence_level',
            'detected_patterns', 'detected_patterns_list', 'risk_factors',
            'risk_factors_dict', 'recommended_actions', 'recommended_actions_list',
            'event_data', 'detection_timestamp'
        ]
        read_only_fields = [
            'id', 'user_id', 'detection_timestamp'
        ]
    
    def validate_risk_score(self, value: float) -> float:
        """Validate risk score with business logic checks."""
        try:
            risk_float = float(value)
            if not 0 <= risk_float <= 1:
                raise serializers.ValidationError("Risk score must be between 0 and 1")
            return risk_float
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid risk score format")
    
    def validate_confidence_level(self, value: float) -> float:
        """Validate confidence level."""
        try:
            confidence_float = float(value)
            if not 0 <= confidence_float <= 1:
                raise serializers.ValidationError("Confidence level must be between 0 and 1")
            return confidence_float
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid confidence level format")
    
    def validate_detected_patterns(self, value: List[str]) -> List[str]:
        """Validate detected patterns with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Detected patterns must be a list")
        
        # Security: Validate pattern names
        valid_patterns = [
            'ml_anomaly', 'suspicious_ip', 'suspicious_user_agent',
            'suspicious_device', 'unusual_location', 'high_frequency',
            'bot_behavior', 'proxy_usage', 'vpn_usage', 'data_center_ip'
        ]
        
        for pattern in value:
            if not isinstance(pattern, str) or pattern not in valid_patterns:
                raise serializers.ValidationError(f"Invalid pattern: {pattern}")
        
        return value
    
    def validate_risk_factors(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate risk factors with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Risk factors must be a dictionary")
        
        # Security: Validate risk factor keys and values
        valid_keys = [
            'ml', 'pattern', 'behavioral', 'technical',
            'ip_address', 'user_agent', 'device', 'geolocation'
        ]
        
        for key, val in value.items():
            if key not in valid_keys:
                raise serializers.ValidationError(f"Invalid risk factor key: {key}")
            
            # Validate risk factor values
            if isinstance(val, (int, float)):
                if not 0 <= val <= 1:
                    raise serializers.ValidationError(f"Risk factor {key} must be between 0 and 1")
            elif isinstance(val, dict):
                # Validate nested risk factors
                for nested_key, nested_val in val.items():
                    if isinstance(nested_val, (int, float)):
                        if not 0 <= nested_val <= 1:
                            raise serializers.ValidationError(f"Nested risk factor {nested_key} must be between 0 and 1")
        
        return value
    
    def validate_recommended_actions(self, value: List[str]) -> List[str]:
        """Validate recommended actions with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Recommended actions must be a list")
        
        # Security: Validate action names
        valid_actions = [
            'block_user', 'limit_access', 'require_verification',
            'monitor_closely', 'manual_review', 'notify_security',
            'block_ip', 'block_device', 'investigate_anomaly'
        ]
        
        for action in value:
            if not isinstance(action, str) or action not in valid_actions:
                raise serializers.ValidationError(f"Invalid action: {action}")
        
        return value
    
    def validate_event_data(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate event data with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Event data must be a dictionary")
        
        # Security: Check for prohibited content
        event_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, event_str, re.IGNORECASE):
                raise serializers.ValidationError("Event data contains prohibited content")
        
        # Validate required event fields
        required_fields = ['event_type', 'timestamp']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"Required event field missing: {field}")
        
        # Validate event type
        valid_event_types = ['login', 'transaction', 'registration', 'campaign_create', 'creative_upload']
        if value.get('event_type') not in valid_event_types:
            raise serializers.ValidationError(f"Invalid event type: {value.get('event_type')}")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Business logic: High risk score should have fraud flag
        risk_score = attrs.get('risk_score', 0)
        is_fraudulent = attrs.get('is_fraudulent', False)
        
        if risk_score > 0.7 and not is_fraudulent:
            raise serializers.ValidationError("High risk score should indicate fraud")
        
        if risk_score < 0.3 and is_fraudulent:
            raise serializers.ValidationError("Low risk score should not indicate fraud")
        
        # Business logic: Fraudulent detection should have patterns
        if is_fraudulent and not attrs.get('detected_patterns', []):
            raise serializers.ValidationError("Fraudulent detection should have detected patterns")
        
        return attrs


class FraudDetectionRequestSerializer(serializers.Serializer):
    """
    Enterprise-grade serializer for fraud detection requests.
    
    Features:
    - Comprehensive input validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    event_type = serializers.ChoiceField(
        choices=['login', 'transaction', 'registration', 'campaign_create', 'creative_upload'],
        required=True
    )
    user_id = serializers.UUIDField(required=False, allow_null=True)
    session_id = serializers.CharField(max_length=255, required=False, allow_blank=True)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    ip_address = serializers.IPAddressField(required=False, allow_blank=True)
    user_agent = serializers.CharField(max_length=500, required=False, allow_blank=True)
    device_fingerprint = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    timestamp = serializers.DateTimeField(required=False)
    custom_data = serializers.JSONField(required=False, default=dict)
    
    def validate_amount(self, value: Optional[Decimal]) -> Optional[Decimal]:
        """Validate transaction amount."""
        if value is not None:
            if value < 0:
                raise serializers.ValidationError("Amount cannot be negative")
            if value > Decimal('1000000'):
                raise serializers.ValidationError("Amount seems unusually high")
        return value
    
    def validate_ip_address(self, value: Optional[str]) -> Optional[str]:
        """Validate IP address with security checks."""
        if value:
            # Security: Check for private IPs
            try:
                import ipaddress
                ip = ipaddress.ip_address(value)
                if ip.is_private:
                    raise serializers.ValidationError("Private IP addresses are not allowed")
            except ValueError:
                raise serializers.ValidationError("Invalid IP address format")
            
            # Security: Check for suspicious patterns
            if any(pattern in value.lower() for pattern in ['proxy', 'vpn', 'tor']):
                raise serializers.ValidationError("Suspicious IP address detected")
        
        return value
    
    def validate_user_agent(self, value: Optional[str]) -> Optional[str]:
        """Validate user agent with security checks."""
        if value:
            # Security: Check for bot patterns
            bot_patterns = [
                'bot', 'crawler', 'spider', 'scraper',
                'curl', 'wget', 'python', 'java'
            ]
            
            if any(pattern in value.lower() for pattern in bot_patterns):
                raise serializers.ValidationError("Suspicious user agent detected")
            
            # Security: Check length
            if len(value) < 10 or len(value) > 500:
                raise serializers.ValidationError("User agent length is unusual")
        
        return value
    
    def validate_device_fingerprint(self, value: Optional[str]) -> Optional[str]:
        """Validate device fingerprint with security checks."""
        if value:
            # Security: Check for automation indicators
            automation_patterns = [
                'selenium', 'webdriver', 'phantomjs', 'headless'
            ]
            
            if any(pattern in value.lower() for pattern in automation_patterns):
                raise serializers.ValidationError("Automation tool detected")
            
            # Security: Check length
            if len(value) < 20 or len(value) > 1000:
                raise serializers.ValidationError("Device fingerprint length is unusual")
        
        return value
    
    def validate_custom_data(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate custom data with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Custom data must be a dictionary")
        
        # Security: Check for prohibited content
        data_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, data_str, re.IGNORECASE):
                raise serializers.ValidationError("Custom data contains prohibited content")
        
        # Validate custom data size
        if len(data_str) > 10000:
            raise serializers.ValidationError("Custom data is too large")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Business logic: Transaction events should have amount
        event_type = attrs.get('event_type')
        amount = attrs.get('amount')
        
        if event_type == 'transaction' and amount is None:
            raise serializers.ValidationError("Transaction events require amount")
        
        # Business logic: High amount transactions require additional validation
        if amount and amount > Decimal('10000'):
            if not attrs.get('user_id'):
                raise serializers.ValidationError("High amount transactions require user ID")
        
        return attrs


class RiskScoreSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for RiskScore model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    user_id_str = serializers.CharField(source='user_id', read_only=True)
    risk_factors_dict = serializers.DictField(source='risk_factors', read_only=True)
    confidence_interval_tuple = serializers.ListField(source='confidence_interval', read_only=True)
    
    class Meta:
        model = RiskScore
        fields = [
            'id', 'user_id', 'user_id_str', 'overall_risk_score', 'risk_level',
            'risk_factors', 'risk_factors_dict', 'temporal_risk',
            'behavioral_risk', 'technical_risk', 'contextual_risk',
            'confidence_interval', 'confidence_interval_tuple',
            'assessment_timestamp'
        ]
        read_only_fields = [
            'id', 'user_id', 'assessment_timestamp'
        ]
    
    def validate_overall_risk_score(self, value: float) -> float:
        """Validate overall risk score."""
        try:
            risk_float = float(value)
            if not 0 <= risk_float <= 1:
                raise serializers.ValidationError("Overall risk score must be between 0 and 1")
            return risk_float
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid overall risk score format")
    
    def validate_risk_level(self, value: str) -> str:
        """Validate risk level."""
        valid_levels = ['low', 'medium', 'high', 'critical']
        if value not in valid_levels:
            raise serializers.ValidationError(f"Risk level must be one of: {valid_levels}")
        return value
    
    def validate_temporal_risk(self, value: float) -> float:
        """Validate temporal risk score."""
        try:
            risk_float = float(value)
            if not 0 <= risk_float <= 1:
                raise serializers.ValidationError("Temporal risk must be between 0 and 1")
            return risk_float
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid temporal risk format")
    
    def validate_behavioral_risk(self, value: float) -> float:
        """Validate behavioral risk score."""
        try:
            risk_float = float(value)
            if not 0 <= risk_float <= 1:
                raise serializers.ValidationError("Behavioral risk must be between 0 and 1")
            return risk_float
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid behavioral risk format")
    
    def validate_technical_risk(self, value: float) -> float:
        """Validate technical risk score."""
        try:
            risk_float = float(value)
            if not 0 <= risk_float <= 1:
                raise serializers.ValidationError("Technical risk must be between 0 and 1")
            return risk_float
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid technical risk format")
    
    def validate_contextual_risk(self, value: float) -> float:
        """Validate contextual risk score."""
        try:
            risk_float = float(value)
            if not 0 <= risk_float <= 1:
                raise serializers.ValidationError("Contextual risk must be between 0 and 1")
            return risk_float
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid contextual risk format")
    
    def validate_confidence_interval(self, value: Tuple[float, float]) -> Tuple[float, float]:
        """Validate confidence interval."""
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise serializers.ValidationError("Confidence interval must be a tuple of two values")
        
        lower, upper = value
        try:
            lower_float = float(lower)
            upper_float = float(upper)
            
            if not 0 <= lower_float <= 1:
                raise serializers.ValidationError("Lower bound must be between 0 and 1")
            if not 0 <= upper_float <= 1:
                raise serializers.ValidationError("Upper bound must be between 0 and 1")
            if lower_float > upper_float:
                raise serializers.ValidationError("Lower bound cannot be greater than upper bound")
            
            return (lower_float, upper_float)
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid confidence interval format")
    
    def validate_risk_factors(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate risk factors."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Risk factors must be a dictionary")
        
        # Validate risk factor values
        for key, val in value.items():
            if isinstance(val, (int, float)):
                if not 0 <= val <= 1:
                    raise serializers.ValidationError(f"Risk factor {key} must be between 0 and 1")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Business logic: Risk level should match overall score
        overall_score = attrs.get('overall_risk_score', 0)
        risk_level = attrs.get('risk_level', 'low')
        
        score_to_level = {
            (0, 0.3): 'low',
            (0.3, 0.6): 'medium',
            (0.6, 0.8): 'high',
            (0.8, 1.0): 'critical'
        }
        
        expected_level = None
        for (min_score, max_score), level in score_to_level.items():
            if min_score <= overall_score < max_score:
                expected_level = level
                break
        
        if expected_level and risk_level != expected_level:
            raise serializers.ValidationError(f"Risk level {risk_level} does not match overall score {overall_score}")
        
        return attrs


class RiskScoreRequestSerializer(serializers.Serializer):
    """
    Enterprise-grade serializer for risk score requests.
    
    Features:
    - Comprehensive input validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    user_id = serializers.UUIDField(required=True)
    context = serializers.JSONField(required=False, default=dict)
    
    def validate_context(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate context with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Context must be a dictionary")
        
        # Security: Check for prohibited content
        context_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, context_str, re.IGNORECASE):
                raise serializers.ValidationError("Context contains prohibited content")
        
        # Validate context size
        if len(context_str) > 5000:
            raise serializers.ValidationError("Context is too large")
        
        return value


class FraudPatternSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for FraudPattern model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = FraudPattern
        fields = [
            'id', 'name', 'pattern_type', 'detection_rules',
            'weight', 'threshold', 'is_active', 'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at'
        ]
    
    def validate_name(self, value: str) -> str:
        """Validate pattern name with security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Pattern name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Pattern name contains prohibited characters")
        
        return value
    
    def validate_pattern_type(self, value: str) -> str:
        """Validate pattern type."""
        valid_types = ['behavioral', 'technical', 'temporal', 'contextual', 'ml_based']
        if value not in valid_types:
            raise serializers.ValidationError(f"Pattern type must be one of: {valid_types}")
        return value
    
    def validate_detection_rules(self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate detection rules with comprehensive checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Detection rules must be a list")
        
        if not value:
            raise serializers.ValidationError("At least one detection rule is required")
        
        # Validate each rule
        for i, rule in enumerate(value):
            if not isinstance(rule, dict):
                raise serializers.ValidationError(f"Rule {i} must be a dictionary")
            
            # Validate required rule fields
            required_fields = ['field', 'operator', 'value', 'risk_score']
            for field in required_fields:
                if field not in rule:
                    raise serializers.ValidationError(f"Rule {i} missing required field: {field}")
            
            # Validate rule fields
            FraudPatternSerializer._validate_rule_field(rule['field'], f"Rule {i} field")
            FraudPatternSerializer._validate_rule_operator(rule['operator'], f"Rule {i} operator")
            FraudPatternSerializer._validate_rule_value(rule['value'], f"Rule {i} value")
            FraudPatternSerializer._validate_rule_risk_score(rule['risk_score'], f"Rule {i} risk_score")
        
        return value
    
    def validate_weight(self, value: float) -> float:
        """Validate pattern weight."""
        try:
            weight_float = float(value)
            if not 0 <= weight_float <= 1:
                raise serializers.ValidationError("Weight must be between 0 and 1")
            return weight_float
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid weight format")
    
    def validate_threshold(self, value: float) -> float:
        """Validate pattern threshold."""
        try:
            threshold_float = float(value)
            if not 0 <= threshold_float <= 1:
                raise serializers.ValidationError("Threshold must be between 0 and 1")
            return threshold_float
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid threshold format")
    
    @staticmethod
    def _validate_rule_field(field: str, context: str) -> None:
        """Validate rule field."""
        valid_fields = [
            'ip_address', 'user_agent', 'device_fingerprint', 'amount',
            'frequency', 'time_of_day', 'day_of_week', 'location'
        ]
        if field not in valid_fields:
            raise serializers.ValidationError(f"{context} must be one of: {valid_fields}")
    
    @staticmethod
    def _validate_rule_operator(operator: str, context: str) -> None:
        """Validate rule operator."""
        valid_operators = [
            'equals', 'not_equals', 'greater_than', 'less_than',
            'contains', 'not_contains', 'in_range', 'regex'
        ]
        if operator not in valid_operators:
            raise serializers.ValidationError(f"{context} must be one of: {valid_operators}")
    
    @staticmethod
    def _validate_rule_value(value: Any, context: str) -> None:
        """Validate rule value."""
        if value is None:
            raise serializers.ValidationError(f"{context} cannot be null")
        
        # Additional validation based on operator type
        # This would be implemented based on specific requirements
    
    @staticmethod
    def _validate_rule_risk_score(risk_score: Any, context: str) -> None:
        """Validate rule risk score."""
        try:
            score_float = float(risk_score)
            if not 0 <= score_float <= 1:
                raise serializers.ValidationError(f"{context} must be between 0 and 1")
        except (ValueError, TypeError):
            raise serializers.ValidationError(f"{context} must be a number")


class SecurityAlertSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for SecurityAlert model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    user_id_str = serializers.CharField(source='user_id', read_only=True)
    threat_data_dict = serializers.DictField(source='threat_data', read_only=True)
    recommended_actions_list = serializers.ListField(source='recommended_actions', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    
    class Meta:
        model = SecurityAlert
        fields = [
            'id', 'alert_type', 'severity', 'title', 'description',
            'user_id', 'user_id_str', 'session_id', 'ip_address',
            'device_fingerprint', 'threat_data', 'threat_data_dict',
            'recommended_actions', 'recommended_actions_list', 'status',
            'created_at', 'updated_at', 'created_by', 'created_by_name',
            'updated_by', 'updated_by_name'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
    
    def validate_alert_type(self, value: str) -> str:
        """Validate alert type."""
        valid_types = ['fraud', 'suspicious_activity', 'security_breach', 'anomaly', 'threat']
        if value not in valid_types:
            raise serializers.ValidationError(f"Alert type must be one of: {valid_types}")
        return value
    
    def validate_severity(self, value: str) -> str:
        """Validate alert severity."""
        valid_severities = ['low', 'medium', 'high', 'critical']
        if value not in valid_severities:
            raise serializers.ValidationError(f"Severity must be one of: {valid_severities}")
        return value
    
    def validate_title(self, value: str) -> str:
        """Validate alert title with security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Title must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'"]
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Title contains prohibited characters")
        
        return value
    
    def validate_description(self, value: str) -> str:
        """Validate alert description with security checks."""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError("Description must be at least 10 characters long")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Description contains prohibited content")
        
        return value.strip()
    
    def validate_status(self, value: str) -> str:
        """Validate alert status."""
        valid_statuses = ['open', 'investigating', 'resolved', 'closed']
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Status must be one of: {valid_statuses}")
        return value
    
    def validate_threat_data(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate threat data with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Threat data must be a dictionary")
        
        # Security: Check for prohibited content
        threat_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, threat_str, re.IGNORECASE):
                raise serializers.ValidationError("Threat data contains prohibited content")
        
        # Validate threat data size
        if len(threat_str) > 10000:
            raise serializers.ValidationError("Threat data is too large")
        
        return value
    
    def validate_recommended_actions(self, value: List[str]) -> List[str]:
        """Validate recommended actions with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Recommended actions must be a list")
        
        # Security: Validate action names
        valid_actions = [
            'block_user', 'limit_access', 'require_verification',
            'monitor_closely', 'manual_review', 'notify_security',
            'block_ip', 'block_device', 'investigate_anomaly'
        ]
        
        for action in value:
            if not isinstance(action, str) or action not in valid_actions:
                raise serializers.ValidationError(f"Invalid action: {action}")
        
        return value


class SecurityAlertRequestSerializer(serializers.Serializer):
    """
    Enterprise-grade serializer for security alert requests.
    
    Features:
    - Comprehensive input validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    alert_type = serializers.ChoiceField(
        choices=['fraud', 'suspicious_activity', 'security_breach', 'anomaly', 'threat'],
        required=True
    )
    severity = serializers.ChoiceField(
        choices=['low', 'medium', 'high', 'critical'],
        default='medium'
    )
    title = serializers.CharField(max_length=255, required=True)
    description = serializers.CharField(required=True)
    user_id = serializers.UUIDField(required=False, allow_null=True)
    session_id = serializers.CharField(max_length=255, required=False, allow_blank=True)
    ip_address = serializers.IPAddressField(required=False, allow_blank=True)
    device_fingerprint = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    threat_data = serializers.JSONField(required=False, default=dict)
    recommended_actions = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )
    
    def validate_title(self, value: str) -> str:
        """Validate alert title."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Title must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'"]
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Title contains prohibited characters")
        
        return value
    
    def validate_description(self, value: str) -> str:
        """Validate alert description."""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError("Description must be at least 10 characters long")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Description contains prohibited content")
        
        return value.strip()
    
    def validate_threat_data(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate threat data."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Threat data must be a dictionary")
        
        # Security: Check for prohibited content
        threat_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, threat_str, re.IGNORECASE):
                raise serializers.ValidationError("Threat data contains prohibited content")
        
        # Validate threat data size
        if len(threat_str) > 10000:
            raise serializers.ValidationError("Threat data is too large")
        
        return value
    
    def validate_recommended_actions(self, value: List[str]) -> List[str]:
        """Validate recommended actions."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Recommended actions must be a list")
        
        # Security: Validate action names
        valid_actions = [
            'block_user', 'limit_access', 'require_verification',
            'monitor_closely', 'manual_review', 'notify_security',
            'block_ip', 'block_device', 'investigate_anomaly'
        ]
        
        for action in value:
            if not isinstance(action, str) or action not in valid_actions:
                raise serializers.ValidationError(f"Invalid action: {action}")
        
        return value


# Request/Response Serializers for API Endpoints

class FraudDetectionResponseSerializer(serializers.Serializer):
    """Serializer for fraud detection responses."""
    
    request_id = serializers.CharField()
    detection_result = serializers.DictField()
    security_context = serializers.DictField()
    processing_time = serializers.FloatField()


class FraudDetectionHistoryResponseSerializer(serializers.Serializer):
    """Serializer for fraud detection history responses."""
    
    items = serializers.ListField(child=serializers.DictField())
    pagination = serializers.DictField()
    filters_applied = serializers.DictField()


class FraudDetectionStatisticsResponseSerializer(serializers.Serializer):
    """Serializer for fraud detection statistics responses."""
    
    summary = serializers.DictField()
    risk_analysis = serializers.DictField()
    pattern_analysis = serializers.DictField()
    trends = serializers.DictField()


class RiskScoreResponseSerializer(serializers.Serializer):
    """Serializer for risk score responses."""
    
    user_id = serializers.UUIDField()
    risk_assessment = serializers.DictField()
    recommendations = serializers.ListField(child=serializers.CharField())


class RiskHistoryResponseSerializer(serializers.Serializer):
    """Serializer for risk history responses."""
    
    items = serializers.ListField(child=serializers.DictField())
    summary = serializers.DictField()


class PatternAnalysisResponseSerializer(serializers.Serializer):
    """Serializer for pattern analysis responses."""
    
    user_id = serializers.UUIDField()
    time_range_days = serializers.IntegerField()
    temporal_patterns = serializers.DictField()
    behavioral_patterns = serializers.DictField()
    technical_patterns = serializers.DictField()
    anomalies = serializers.ListField(child=serializers.DictField())
    analysis_timestamp = serializers.DateTimeField()


class PatternDashboardResponseSerializer(serializers.Serializer):
    """Serializer for pattern dashboard responses."""
    
    summary = serializers.DictField()
    risk_distribution = serializers.DictField()
    pattern_trends = serializers.ListField(child=serializers.DictField())
    generated_at = serializers.DateTimeField()


class SecurityAlertCreateResponseSerializer(serializers.Serializer):
    """Serializer for security alert creation responses."""
    
    alert_id = serializers.UUIDField()
    alert_type = serializers.CharField()
    severity = serializers.CharField()
    title = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class SecurityAlertsResponseSerializer(serializers.Serializer):
    """Serializer for security alerts responses."""
    
    alerts = serializers.ListField(child=serializers.DictField())


class SecurityAlertUpdateResponseSerializer(serializers.Serializer):
    """Serializer for security alert update responses."""
    
    message = serializers.CharField()


class ComprehensiveAnalysisResponseSerializer(serializers.Serializer):
    """Serializer for comprehensive fraud analysis responses."""
    
    event_data = serializers.DictField()
    context = serializers.DictField()
    analysis_timestamp = serializers.DateTimeField()
    fraud_detection = serializers.DictField()
    risk_assessment = serializers.DictField()
    pattern_analysis = serializers.DictField()
    security_alerts = serializers.ListField(child=serializers.DictField())
    recommendations = serializers.ListField(child=serializers.CharField())


class FraudPreventionDashboardResponseSerializer(serializers.Serializer):
    """Serializer for fraud prevention dashboard responses."""
    
    summary = serializers.DictField()
    risk_distribution = serializers.DictField()
    recent_activity = serializers.ListField(child=serializers.DictField())
    threat_intelligence = serializers.DictField()
    generated_at = serializers.DateTimeField()


# Comprehensive Response Serializers

class FraudDetectionCreateResponseSerializer(serializers.Serializer):
    """Serializer for fraud detection creation responses."""
    
    id = serializers.UUIDField()
    user_id = serializers.UUIDField()
    session_id = serializers.CharField()
    event_type = serializers.CharField()
    risk_score = serializers.FloatField()
    is_fraudulent = serializers.BooleanField()
    confidence_level = serializers.FloatField()
    detected_patterns = serializers.ListField(child=serializers.CharField())
    risk_factors = serializers.DictField()
    recommended_actions = serializers.ListField(child=serializers.CharField())
    detection_timestamp = serializers.DateTimeField()


class RiskScoreCreateResponseSerializer(serializers.Serializer):
    """Serializer for risk score creation responses."""
    
    id = serializers.UUIDField()
    user_id = serializers.UUIDField()
    overall_risk_score = serializers.FloatField()
    risk_level = serializers.CharField()
    risk_factors = serializers.DictField()
    temporal_risk = serializers.FloatField()
    behavioral_risk = serializers.FloatField()
    technical_risk = serializers.FloatField()
    contextual_risk = serializers.FloatField()
    confidence_interval = serializers.ListField(child=serializers.FloatField())
    assessment_timestamp = serializers.DateTimeField()


class SecurityAlertCreateResponseSerializer(serializers.Serializer):
    """Serializer for security alert creation responses."""
    
    id = serializers.UUIDField()
    alert_type = serializers.CharField()
    severity = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    user_id = serializers.UUIDField()
    session_id = serializers.CharField()
    ip_address = serializers.CharField()
    device_fingerprint = serializers.CharField()
    threat_data = serializers.DictField()
    recommended_actions = serializers.ListField(child=serializers.CharField())
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class FraudPatternCreateResponseSerializer(serializers.Serializer):
    """Serializer for fraud pattern creation responses."""
    
    id = serializers.UUIDField()
    name = serializers.CharField()
    pattern_type = serializers.CharField()
    detection_rules = serializers.ListField(child=serializers.DictField())
    weight = serializers.FloatField()
    threshold = serializers.FloatField()
    is_active = serializers.BooleanField()
    created_at = serializers.DateTimeField()
