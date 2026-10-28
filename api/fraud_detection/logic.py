# =============================================================================
# fraud_detection/logic.py
# =============================================================================
"""
Business Logic Layer for Fraud Detection System.

Provides core business logic, decision trees, and
fraud detection algorithms with comprehensive rule processing.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal

from django.utils import timezone
from django.db.models import Q
from django.core.cache import cache

from api.fraud_detection.abstracts import (
    BaseFraudDetector, BaseRiskAssessor, DetectionStrategy, RiskLevel,
    DetectionContext, DetectionResult
)
from api.fraud_detection.exceptions import FraudDetectionError
from api.fraud_detection.constants import RISK_THRESHOLDS, FRAUD_SCORE_WEIGHTS


logger = logging.getLogger(__name__)


class LogicOperator(Enum):
    """Logic operators for rule evaluation."""
    AND = "and"
    OR = "or"
    NOT = "not"
    XOR = "xor"


class ComparisonOperator(Enum):
    """Comparison operators for conditions."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUAL = "greater_equal"
    LESS_EQUAL = "less_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IN = "in"
    NOT_IN = "not_in"
    BETWEEN = "between"
    REGEX = "regex"


@dataclass
class Condition:
    """Condition for rule evaluation."""
    field: str
    operator: ComparisonOperator
    value: Any
    weight: float = 1.0
    
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Evaluate condition against data."""
        field_value = self._get_field_value(data, self.field)
        
        try:
            if self.operator == ComparisonOperator.EQUALS:
                return field_value == self.value
            elif self.operator == ComparisonOperator.NOT_EQUALS:
                return field_value != self.value
            elif self.operator == ComparisonOperator.GREATER_THAN:
                return float(field_value) > float(self.value)
            elif self.operator == ComparisonOperator.LESS_THAN:
                return float(field_value) < float(self.value)
            elif self.operator == ComparisonOperator.GREATER_EQUAL:
                return float(field_value) >= float(self.value)
            elif self.operator == ComparisonOperator.LESS_EQUAL:
                return float(field_value) <= float(self.value)
            elif self.operator == ComparisonOperator.CONTAINS:
                return str(self.value).lower() in str(field_value).lower()
            elif self.operator == ComparisonOperator.NOT_CONTAINS:
                return str(self.value).lower() not in str(field_value).lower()
            elif self.operator == ComparisonOperator.STARTS_WITH:
                return str(field_value).lower().startswith(str(self.value).lower())
            elif self.operator == ComparisonOperator.ENDS_WITH:
                return str(field_value).lower().endswith(str(self.value).lower())
            elif self.operator == ComparisonOperator.IN:
                return field_value in self.value
            elif self.operator == ComparisonOperator.NOT_IN:
                return field_value not in self.value
            elif self.operator == ComparisonOperator.BETWEEN:
                if isinstance(self.value, (list, tuple)) and len(self.value) == 2:
                    return float(self.value[0]) <= float(field_value) <= float(self.value[1])
                return False
            elif self.operator == ComparisonOperator.REGEX:
                import re
                pattern = re.compile(str(self.value), re.IGNORECASE)
                return bool(pattern.search(str(field_value)))
            else:
                return False
                
        except (ValueError, TypeError, AttributeError):
            return False
    
    def _get_field_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """Get field value from nested data."""
        keys = field_path.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value


@dataclass
class Rule:
    """Fraud detection rule."""
    name: str
    description: str
    conditions: List[Condition]
    logic_operator: LogicOperator = LogicOperator.AND
    risk_score_impact: int = 0
    confidence_score: float = 1.0
    enabled: bool = True
    priority: int = 50
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    def evaluate(self, data: Dict[str, Any]) -> Tuple[bool, float]:
        """
        Evaluate rule against data.
        
        Returns:
            Tuple of (rule_matched, confidence_score)
        """
        if not self.enabled:
            return False, 0.0
        
        if not self.conditions:
            return False, 0.0
        
        condition_results = []
        total_weight = 0.0
        
        for condition in self.conditions:
            result = condition.evaluate(data)
            condition_results.append(result)
            total_weight += condition.weight
        
        # Apply logic operator
        if self.logic_operator == LogicOperator.AND:
            rule_matched = all(condition_results)
        elif self.logic_operator == LogicOperator.OR:
            rule_matched = any(condition_results)
        elif self.logic_operator == LogicOperator.NOT:
            rule_matched = not all(condition_results)
        elif self.logic_operator == LogicOperator.XOR:
            rule_matched = sum(condition_results) == 1
        else:
            rule_matched = False
        
        # Calculate confidence based on condition weights
        if condition_results:
            matched_weight = sum(
                condition.weight for condition, result in zip(self.conditions, condition_results)
                if result
            )
            confidence = (matched_weight / total_weight) * self.confidence_score
        else:
            confidence = 0.0
        
        return rule_matched, confidence


class DecisionNode:
    """Node in decision tree."""
    
    def __init__(self, name: str, condition: Optional[Condition] = None):
        """Initialize decision node."""
        self.name = name
        self.condition = condition
        self.true_branch = None
        self.false_branch = None
        self.outcome = None
        self.description = ""
    
    def evaluate(self, data: Dict[str, Any]) -> Any:
        """Evaluate decision node."""
        if self.condition is None:
            return self.outcome
        
        condition_result = self.condition.evaluate(data)
        
        if condition_result and self.true_branch:
            return self.true_branch.evaluate(data)
        elif not condition_result and self.false_branch:
            return self.false_branch.evaluate(data)
        else:
            return self.outcome
    
    def add_true_branch(self, node: 'DecisionNode'):
        """Add true branch."""
        self.true_branch = node
    
    def add_false_branch(self, node: 'DecisionNode'):
        """Add false branch."""
        self.false_branch = node
    
    def set_outcome(self, outcome: Any):
        """Set node outcome."""
        self.outcome = outcome


class RuleBasedDetector(BaseFraudDetector):
    """Rule-based fraud detector."""
    
    def __init__(self, name: str = "rule_based_detector"):
        """Initialize rule-based detector."""
        super().__init__(name, DetectionStrategy.RULE_BASED)
        self.rules = []
        self.decision_tree = None
        self.rule_cache = {}
        self.cache_timeout = 300  # 5 minutes
    
    def add_rule(self, rule: Rule):
        """Add rule to detector."""
        self.rules.append(rule)
        # Sort by priority (higher first)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    def remove_rule(self, rule_name: str) -> bool:
        """Remove rule by name."""
        for i, rule in enumerate(self.rules):
            if rule.name == rule_name:
                del self.rules[i]
                return True
        return False
    
    def set_decision_tree(self, root_node: DecisionNode):
        """Set decision tree."""
        self.decision_tree = root_node
    
    def detect(self, context: DetectionContext, data: Dict[str, Any]) -> DetectionResult:
        """Detect fraud using rules."""
        start_time = timezone.now()
        
        # Check cache first
        cache_key = self._generate_cache_key(context, data)
        cached_result = self.rule_cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        # Evaluate rules
        matched_rules = []
        total_risk_score = 0
        indicators = []
        recommendations = []
        
        for rule in self.rules:
            rule_matched, confidence = rule.evaluate(data)
            
            if rule_matched:
                matched_rules.append({
                    'name': rule.name,
                    'confidence': confidence,
                    'risk_impact': rule.risk_score_impact
                })
                
                total_risk_score += rule.risk_score_impact
                indicators.append(rule.name)
                
                if rule.risk_score_impact >= 50:
                    recommendations.append(f"Review rule: {rule.name}")
        
        # Evaluate decision tree if available
        tree_result = None
        if self.decision_tree:
            tree_result = self.decision_tree.evaluate(data)
            if isinstance(tree_result, dict):
                total_risk_score += tree_result.get('risk_score', 0)
                indicators.extend(tree_result.get('indicators', []))
                recommendations.extend(tree_result.get('recommendations', []))
        
        # Cap risk score at 100
        total_risk_score = min(total_risk_score, 100)
        
        # Determine risk level
        risk_level = self._determine_risk_level(total_risk_score)
        
        # Calculate confidence
        confidence_score = self._calculate_confidence(matched_rules)
        
        # Create detection result
        result = DetectionResult(
            fraud_detected=total_risk_score >= RISK_THRESHOLDS['high'],
            risk_score=total_risk_score,
            risk_level=risk_level,
            confidence_score=confidence_score,
            indicators=indicators,
            recommendations=recommendations,
            processing_time_ms=0,  # Will be set by base class
            detection_method=self.strategy,
            context=context,
            metadata={
                'matched_rules': matched_rules,
                'tree_result': tree_result,
                'rules_evaluated': len(self.rules)
            }
        )
        
        # Cache result
        self.rule_cache[cache_key] = result
        
        return result
    
    def train(self, training_data: List[Dict[str, Any]]) -> bool:
        """Train rule-based detector (optimization of rules)."""
        try:
            # Analyze training data to optimize rule weights
            rule_performance = {}
            
            for rule in self.rules:
                true_positives = 0
                false_positives = 0
                total_evaluations = 0
                
                for data_point in training_data:
                    rule_matched, _ = rule.evaluate(data_point)
                    is_fraud = data_point.get('is_fraud', False)
                    
                    total_evaluations += 1
                    if rule_matched and is_fraud:
                        true_positives += 1
                    elif rule_matched and not is_fraud:
                        false_positives += 1
                
                # Calculate precision
                precision = true_positives / max(true_positives + false_positives, 1)
                
                rule_performance[rule.name] = {
                    'precision': precision,
                    'true_positives': true_positives,
                    'false_positives': false_positives,
                    'total_evaluations': total_evaluations
                }
                
                # Adjust rule weight based on performance
                if precision < 0.5:
                    rule.confidence_score *= 0.8  # Reduce confidence for poor performers
                elif precision > 0.8:
                    rule.confidence_score *= 1.2  # Increase confidence for good performers
            
            logger.info(f"Rule-based detector trained with {len(training_data)} samples")
            return True
            
        except Exception as e:
            logger.error(f"Training failed for rule-based detector: {e}")
            return False
    
    def validate_configuration(self) -> bool:
        """Validate detector configuration."""
        if not self.rules:
            logger.warning("No rules configured for rule-based detector")
            return False
        
        # Validate each rule
        for rule in self.rules:
            if not rule.conditions:
                logger.error(f"Rule {rule.name} has no conditions")
                return False
            
            for condition in rule.conditions:
                if not isinstance(condition.operator, ComparisonOperator):
                    logger.error(f"Invalid operator in rule {rule.name}")
                    return False
        
        return True
    
    def _generate_cache_key(self, context: DetectionContext, data: Dict[str, Any]) -> str:
        """Generate cache key for detection result."""
        import hashlib
        
        key_data = f"{context.user_id}_{hash(str(data))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _determine_risk_level(self, risk_score: int) -> RiskLevel:
        """Determine risk level from score."""
        if risk_score >= RISK_THRESHOLDS['critical']:
            return RiskLevel.CRITICAL
        elif risk_score >= RISK_THRESHOLDS['very_high']:
            return RiskLevel.VERY_HIGH
        elif risk_score >= RISK_THRESHOLDS['high']:
            return RiskLevel.HIGH
        elif risk_score >= RISK_THRESHOLDS['medium']:
            return RiskLevel.MEDIUM
        elif risk_score >= RISK_THRESHOLDS['low']:
            return RiskLevel.LOW
        else:
            return RiskLevel.VERY_LOW
    
    def _calculate_confidence(self, matched_rules: List[Dict[str, Any]]) -> float:
        """Calculate overall confidence from matched rules."""
        if not matched_rules:
            return 0.0
        
        total_confidence = sum(rule['confidence'] for rule in matched_rules)
        return min(total_confidence / len(matched_rules), 1.0)


class StatisticalDetector(BaseFraudDetector):
    """Statistical fraud detector using anomaly detection."""
    
    def __init__(self, name: str = "statistical_detector"):
        """Initialize statistical detector."""
        super().__init__(name, DetectionStrategy.STATISTICAL)
        self.baseline_stats = {}
        self.anomaly_threshold = 2.0  # Standard deviations
        self.min_sample_size = 100
    
    def detect(self, context: DetectionContext, data: Dict[str, Any]) -> DetectionResult:
        """Detect fraud using statistical analysis."""
        indicators = []
        risk_score = 0
        anomaly_count = 0
        
        # Analyze transaction amount
        amount = data.get('amount', 0)
        if amount > 0:
            amount_anomaly = self._detect_amount_anomaly(amount)
            if amount_anomaly['is_anomaly']:
                indicators.append("unusual_amount")
                risk_score += 30
                anomaly_count += 1
        
        # Analyze transaction frequency
        frequency_anomaly = self._detect_frequency_anomaly(context.user_id)
        if frequency_anomaly['is_anomaly']:
            indicators.append("unusual_frequency")
            risk_score += 25
            anomaly_count += 1
        
        # Analyze location patterns
        ip_address = data.get('ip_address')
        if ip_address:
            location_anomaly = self._detect_location_anomaly(context.user_id, ip_address)
            if location_anomaly['is_anomaly']:
                indicators.append("unusual_location")
                risk_score += 20
                anomaly_count += 1
        
        # Analyze time patterns
        timestamp = data.get('timestamp', timezone.now())
        time_anomaly = self._detect_time_anomaly(context.user_id, timestamp)
        if time_anomaly['is_anomaly']:
            indicators.append("unusual_timing")
            risk_score += 15
            anomaly_count += 1
        
        # Calculate confidence based on anomaly count
        confidence_score = min(anomaly_count * 0.3, 1.0)
        
        # Determine risk level
        risk_level = self._determine_risk_level(risk_score)
        
        # Generate recommendations
        recommendations = []
        if risk_score >= 50:
            recommendations.append("Manual review recommended")
        if anomaly_count >= 3:
            recommendations.append("Investigate multiple anomalies")
        
        return DetectionResult(
            fraud_detected=risk_score >= RISK_THRESHOLDS['high'],
            risk_score=min(risk_score, 100),
            risk_level=risk_level,
            confidence_score=confidence_score,
            indicators=indicators,
            recommendations=recommendations,
            processing_time_ms=0,
            detection_method=self.strategy,
            context=context,
            metadata={
                'anomaly_count': anomaly_count,
                'anomalies': {
                    'amount': amount_anomaly if amount > 0 else None,
                    'frequency': frequency_anomaly,
                    'location': location_anomaly if ip_address else None,
                    'time': time_anomaly
                }
            }
        )
    
    def train(self, training_data: List[Dict[str, Any]]) -> bool:
        """Train statistical detector with baseline data."""
        try:
            if len(training_data) < self.min_sample_size:
                logger.warning(f"Insufficient training data: {len(training_data)} < {self.min_sample_size}")
                return False
            
            # Calculate baseline statistics
            amounts = [float(item.get('amount', 0)) for item in training_data if item.get('amount', 0) > 0]
            
            if amounts:
                self.baseline_stats['amount'] = {
                    'mean': sum(amounts) / len(amounts),
                    'std': self._calculate_std(amounts),
                    'min': min(amounts),
                    'max': max(amounts),
                    'count': len(amounts)
                }
            
            # Calculate frequency statistics
            user_frequencies = {}
            for item in training_data:
                user_id = item.get('user_id')
                if user_id:
                    user_frequencies[user_id] = user_frequencies.get(user_id, 0) + 1
            
            if user_frequencies:
                frequencies = list(user_frequencies.values())
                self.baseline_stats['frequency'] = {
                    'mean': sum(frequencies) / len(frequencies),
                    'std': self._calculate_std(frequencies),
                    'min': min(frequencies),
                    'max': max(frequencies),
                    'count': len(frequencies)
                }
            
            logger.info(f"Statistical detector trained with {len(training_data)} samples")
            return True
            
        except Exception as e:
            logger.error(f"Training failed for statistical detector: {e}")
            return False
    
    def validate_configuration(self) -> bool:
        """Validate detector configuration."""
        if not self.baseline_stats:
            logger.warning("No baseline statistics available")
            return False
        
        return True
    
    def _detect_amount_anomaly(self, amount: float) -> Dict[str, Any]:
        """Detect amount anomaly."""
        if 'amount' not in self.baseline_stats:
            return {'is_anomaly': False, 'reason': 'No baseline data'}
        
        stats = self.baseline_stats['amount']
        mean = stats['mean']
        std = stats['std']
        
        if std == 0:
            return {'is_anomaly': False, 'reason': 'No variance in baseline'}
        
        z_score = abs(amount - mean) / std
        is_anomaly = z_score > self.anomaly_threshold
        
        return {
            'is_anomaly': is_anomaly,
            'z_score': z_score,
            'amount': amount,
            'baseline_mean': mean,
            'baseline_std': std
        }
    
    def _detect_frequency_anomaly(self, user_id: Union[int, str]) -> Dict[str, Any]:
        """Detect frequency anomaly for user."""
        # This would typically query recent transaction history
        # For now, return a mock result
        return {
            'is_anomaly': False,
            'frequency': 1,
            'baseline_mean': 2.5,
            'reason': 'Mock implementation'
        }
    
    def _detect_location_anomaly(self, user_id: Union[int, str], ip_address: str) -> Dict[str, Any]:
        """Detect location anomaly for user."""
        # This would typically check user's historical locations
        # For now, return a mock result
        return {
            'is_anomaly': False,
            'ip_address': ip_address,
            'known_locations': ['192.168.1.1'],
            'reason': 'Mock implementation'
        }
    
    def _detect_time_anomaly(self, user_id: Union[int, str], timestamp: datetime) -> Dict[str, Any]:
        """Detect time anomaly for user."""
        # This would typically check user's transaction time patterns
        # For now, return a mock result
        hour = timestamp.hour
        is_anomaly = hour < 6 or hour > 22  # Unusual hours
        
        return {
            'is_anomaly': is_anomaly,
            'hour': hour,
            'typical_hours': [9, 10, 11, 14, 15, 16, 17, 18],
            'reason': 'Unusual transaction time'
        }
    
    def _calculate_std(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)
    
    def _determine_risk_level(self, risk_score: int) -> RiskLevel:
        """Determine risk level from score."""
        if risk_score >= 80:
            return RiskLevel.CRITICAL
        elif risk_score >= 60:
            return RiskLevel.HIGH
        elif risk_score >= 40:
            return RiskLevel.MEDIUM
        elif risk_score >= 20:
            return RiskLevel.LOW
        else:
            return RiskLevel.VERY_LOW


class RiskAssessmentLogic(BaseRiskAssessor):
    """Risk assessment business logic."""
    
    def __init__(self, name: str = "risk_assessment_logic"):
        """Initialize risk assessor."""
        super().__init__(name)
        self.risk_factors = {
            'account_age': -0.3,  # Negative weight (older is better)
            'transaction_amount': 0.4,
            'frequency_anomaly': 0.5,
            'location_anomaly': 0.3,
            'device_anomaly': 0.2,
            'time_anomaly': 0.1,
            'historical_fraud': 0.8,
            'sanctions_hit': 0.9
        }
        
        self.weights = self.risk_factors.copy()
    
    def assess_risk(self, context: DetectionContext, 
                    historical_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Assess user risk comprehensively."""
        risk_factors = {}
        total_score = 50  # Base score
        
        # Account age factor
        if historical_data:
            account_age_days = historical_data.get('account_age_days', 0)
            age_score = self._calculate_account_age_risk(account_age_days)
            risk_factors['account_age'] = age_score
            total_score += age_score * self.weights['account_age']
        
        # Transaction patterns
        if historical_data:
            transaction_patterns = historical_data.get('transaction_patterns', {})
            pattern_score = self._analyze_transaction_patterns(transaction_patterns)
            risk_factors['transaction_patterns'] = pattern_score
            total_score += pattern_score * 0.3
        
        # Location consistency
        location_score = self._assess_location_consistency(context, historical_data)
        risk_factors['location_consistency'] = location_score
        total_score += location_score * self.weights['location_anomaly']
        
        # Device consistency
        device_score = self._assess_device_consistency(context, historical_data)
        risk_factors['device_consistency'] = device_score
        total_score += device_score * self.weights['device_anomaly']
        
        # Time patterns
        time_score = self._assess_time_patterns(context, historical_data)
        risk_factors['time_patterns'] = time_score
        total_score += time_score * self.weights['time_anomaly']
        
        # Historical fraud indicators
        if historical_data:
            fraud_history = historical_data.get('fraud_history', {})
            history_score = self._assess_fraud_history(fraud_history)
            risk_factors['fraud_history'] = history_score
            total_score += history_score * self.weights['historical_fraud']
        
        # Cap and normalize score
        total_score = max(0, min(100, total_score))
        
        # Determine risk level
        risk_level = self.get_risk_level(int(total_score))
        
        # Generate recommendations
        recommendations = self._generate_risk_recommendations(total_score, risk_factors)
        
        return {
            'risk_score': int(total_score),
            'risk_level': risk_level.value,
            'risk_factors': risk_factors,
            'recommendations': recommendations,
            'assessment_timestamp': context.timestamp.isoformat(),
            'confidence': self._calculate_assessment_confidence(risk_factors)
        }
    
    def calculate_risk_score(self, factors: Dict[str, Any]) -> int:
        """Calculate risk score from factors."""
        total_score = 50  # Base score
        
        for factor_name, factor_value in factors.items():
            weight = self.weights.get(factor_name, 0)
            total_score += factor_value * weight
        
        return max(0, min(100, int(total_score)))
    
    def get_risk_level(self, risk_score: int) -> RiskLevel:
        """Get risk level from score."""
        if risk_score >= 80:
            return RiskLevel.CRITICAL
        elif risk_score >= 60:
            return RiskLevel.VERY_HIGH
        elif risk_score >= 45:
            return RiskLevel.HIGH
        elif risk_score >= 30:
            return RiskLevel.MEDIUM
        elif risk_score >= 15:
            return RiskLevel.LOW
        else:
            return RiskLevel.VERY_LOW
    
    def _calculate_account_age_risk(self, account_age_days: int) -> float:
        """Calculate risk based on account age."""
        if account_age_days < 7:
            return 30  # High risk for very new accounts
        elif account_age_days < 30:
            return 20  # Medium risk for new accounts
        elif account_age_days < 90:
            return 10  # Low risk for recent accounts
        else:
            return 0   # No risk for established accounts
    
    def _analyze_transaction_patterns(self, patterns: Dict[str, Any]) -> float:
        """Analyze transaction patterns for risk."""
        risk_score = 0
        
        # Analyze transaction frequency
        avg_frequency = patterns.get('avg_daily_transactions', 1)
        if avg_frequency > 10:
            risk_score += 15
        elif avg_frequency > 5:
            risk_score += 10
        
        # Analyze transaction amounts
        avg_amount = patterns.get('avg_amount', 0)
        max_amount = patterns.get('max_amount', 0)
        
        if max_amount > avg_amount * 10:
            risk_score += 20  # Unusually large transaction
        
        # Analyze velocity
        recent_velocity = patterns.get('recent_velocity', 0)
        if recent_velocity > 1000:  # High dollar velocity
            risk_score += 25
        
        return min(risk_score, 50)
    
    def _assess_location_consistency(self, context: DetectionContext, 
                                  historical_data: Optional[Dict[str, Any]]) -> float:
        """Assess location consistency."""
        if not historical_data or not context.ip_address:
            return 0
        
        known_locations = historical_data.get('known_locations', [])
        
        if not known_locations:
            return 10  # No history, slight risk
        
        # Check if current IP is known
        if context.ip_address in known_locations:
            return 0  # Known location, no risk
        else:
            return 20  # Unknown location, moderate risk
    
    def _assess_device_consistency(self, context: DetectionContext, 
                                 historical_data: Optional[Dict[str, Any]]) -> float:
        """Assess device consistency."""
        if not historical_data or not context.user_agent:
            return 0
        
        known_devices = historical_data.get('known_devices', [])
        
        if not known_devices:
            return 5  # No history, slight risk
        
        # Check if current device is known
        if context.user_agent in known_devices:
            return 0  # Known device, no risk
        else:
            return 15  # Unknown device, moderate risk
    
    def _assess_time_patterns(self, context: DetectionContext, 
                            historical_data: Optional[Dict[str, Any]]) -> float:
        """Assess time patterns."""
        hour = context.timestamp.hour
        
        # Define business hours (9 AM - 6 PM)
        if 9 <= hour <= 18:
            return 0  # Business hours, no risk
        elif 19 <= hour <= 22:
            return 5  # Evening, slight risk
        else:  # 11 PM - 8 AM
            return 15  # Unusual hours, moderate risk
    
    def _assess_fraud_history(self, fraud_history: Dict[str, Any]) -> float:
        """Assess fraud history risk."""
        previous_fraud_count = fraud_history.get('previous_fraud_count', 0)
        days_since_last_fraud = fraud_history.get('days_since_last_fraud', 365)
        
        if previous_fraud_count == 0:
            return 0  # No fraud history
        
        risk_score = previous_fraud_count * 20
        
        # Reduce risk if long time since last fraud
        if days_since_last_fraud > 365:
            risk_score *= 0.5
        elif days_since_last_fraud > 180:
            risk_score *= 0.7
        
        return min(risk_score, 80)
    
    def _generate_risk_recommendations(self, risk_score: float, 
                                     risk_factors: Dict[str, Any]) -> List[str]:
        """Generate risk-based recommendations."""
        recommendations = []
        
        if risk_score >= 80:
            recommendations.extend([
                "Immediate manual review required",
                "Consider account suspension",
                "Enhanced monitoring recommended"
            ])
        elif risk_score >= 60:
            recommendations.extend([
                "Manual review recommended",
                "Additional verification required"
            ])
        elif risk_score >= 40:
            recommendations.append("Monitor account activity closely")
        
        # Factor-specific recommendations
        if risk_factors.get('account_age', 0) > 20:
            recommendations.append("New account - verify identity")
        
        if risk_factors.get('location_consistency', 0) > 15:
            recommendations.append("Unusual location - verify user")
        
        if risk_factors.get('device_consistency', 0) > 10:
            recommendations.append("New device - authenticate user")
        
        return recommendations
    
    def _calculate_assessment_confidence(self, risk_factors: Dict[str, Any]) -> float:
        """Calculate confidence in risk assessment."""
        factor_count = len(risk_factors)
        
        if factor_count == 0:
            return 0.1  # Very low confidence with no factors
        
        # More factors = higher confidence
        base_confidence = min(factor_count * 0.15, 0.8)
        
        # Add some randomness for realism
        import random
        confidence = base_confidence + random.uniform(-0.1, 0.1)
        
        return max(0.1, min(1.0, confidence))


# Logic engine for combining multiple detection methods
class HybridDetectionLogic(BaseFraudDetector):
    """Hybrid detection combining multiple methods."""
    
    def __init__(self, name: str = "hybrid_detector"):
        """Initialize hybrid detector."""
        super().__init__(name, DetectionStrategy.HYBRID)
        self.detectors = []
        self.weights = {}
    
    def add_detector(self, detector: BaseFraudDetector, weight: float = 1.0):
        """Add detector to hybrid system."""
        self.detectors.append(detector)
        self.weights[detector.name] = weight
    
    def detect(self, context: DetectionContext, data: Dict[str, Any]) -> DetectionResult:
        """Detect fraud using multiple detectors."""
        all_indicators = []
        all_recommendations = []
        detector_results = []
        
        total_risk_score = 0
        total_weight = 0
        
        # Run all detectors
        for detector in self.detectors:
            try:
                result = detector.detect(context, data)
                detector_results.append({
                    'detector': detector.name,
                    'result': result
                })
                
                # Combine results
                weight = self.weights.get(detector.name, 1.0)
                total_risk_score += result.risk_score * weight
                total_weight += weight
                
                all_indicators.extend(result.indicators)
                all_recommendations.extend(result.recommendations)
                
            except Exception as e:
                logger.error(f"Detector {detector.name} failed: {e}")
        
        # Calculate weighted average risk score
        if total_weight > 0:
            final_risk_score = total_risk_score / total_weight
        else:
            final_risk_score = 0
        
        # Determine risk level
        risk_level = self._determine_risk_level(int(final_risk_score))
        
        # Calculate confidence based on detector agreement
        confidence_score = self._calculate_detector_confidence(detector_results)
        
        # Remove duplicate indicators and recommendations
        unique_indicators = list(set(all_indicators))
        unique_recommendations = list(set(all_recommendations))
        
        return DetectionResult(
            fraud_detected=final_risk_score >= RISK_THRESHOLDS['high'],
            risk_score=int(final_risk_score),
            risk_level=risk_level,
            confidence_score=confidence_score,
            indicators=unique_indicators,
            recommendations=unique_recommendations,
            processing_time_ms=0,
            detection_method=self.strategy,
            context=context,
            metadata={
                'detector_results': detector_results,
                'detector_count': len(self.detectors),
                'weights_used': self.weights
            }
        )
    
    def train(self, training_data: List[Dict[str, Any]]) -> bool:
        """Train all detectors."""
        success = True
        
        for detector in self.detectors:
            try:
                detector_success = detector.train(training_data)
                success = success and detector_success
            except Exception as e:
                logger.error(f"Training failed for detector {detector.name}: {e}")
                success = False
        
        return success
    
    def validate_configuration(self) -> bool:
        """Validate all detector configurations."""
        if not self.detectors:
            logger.error("No detectors configured for hybrid detector")
            return False
        
        all_valid = True
        for detector in self.detectors:
            try:
                detector_valid = detector.validate_configuration()
                all_valid = all_valid and detector_valid
            except Exception as e:
                logger.error(f"Validation failed for detector {detector.name}: {e}")
                all_valid = False
        
        return all_valid
    
    def _determine_risk_level(self, risk_score: int) -> RiskLevel:
        """Determine risk level from score."""
        if risk_score >= 80:
            return RiskLevel.CRITICAL
        elif risk_score >= 60:
            return RiskLevel.HIGH
        elif risk_score >= 40:
            return RiskLevel.MEDIUM
        elif risk_score >= 20:
            return RiskLevel.LOW
        else:
            return RiskLevel.VERY_LOW
    
    def _calculate_detector_confidence(self, detector_results: List[Dict[str, Any]]) -> float:
        """Calculate confidence based on detector agreement."""
        if not detector_results:
            return 0.0
        
        # Check if detectors agree on fraud detection
        fraud_detections = [r['result'].fraud_detected for r in detector_results]
        
        if not fraud_detections:
            return 0.0
        
        # Calculate agreement rate
        agreement = sum(fraud_detections) / len(fraud_detections)
        
        # Higher confidence when detectors agree
        if agreement >= 0.8 or agreement <= 0.2:
            return 0.9
        elif agreement >= 0.6 or agreement <= 0.4:
            return 0.7
        else:
            return 0.5


# Global instances
rule_based_detector = RuleBasedDetector()
statistical_detector = StatisticalDetector()
risk_assessor = RiskAssessmentLogic()
hybrid_detector = HybridDetectionLogic()

# Add detectors to hybrid system
hybrid_detector.add_detector(rule_based_detector, weight=0.6)
hybrid_detector.add_detector(statistical_detector, weight=0.4)
