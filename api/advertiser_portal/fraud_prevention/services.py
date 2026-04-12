"""
Fraud Prevention Services

This module handles fraud prevention operations with enterprise-grade security,
real-time detection, and comprehensive analysis following industry standards
from Stripe, OgAds, and leading fraud prevention systems.
"""

from typing import Optional, List, Dict, Any, Union, Tuple, Set
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID
import json
import math
import hashlib
import hmac
import re
from dataclasses import dataclass
from enum import Enum
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from django.core.cache import cache

from django.db import transaction, connection
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Count, Sum, Avg, StdDev, Q, F, Window, Case, When
from django.db.models.functions import Coalesce, RowNumber, Lead, Lag
from django.contrib.gis.geoip2 import GeoIP2

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.creative_model import Creative
from ..database_models.fraud_model import FraudDetection, RiskScore, FraudPattern, SecurityAlert
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


@dataclass
class FraudDetectionResult:
    """Result of fraud detection analysis."""
    is_fraudulent: bool
    risk_score: float
    confidence_level: float
    detected_patterns: List[str]
    risk_factors: Dict[str, Any]
    recommended_actions: List[str]
    detection_timestamp: datetime
    session_id: Optional[str] = None
    user_id: Optional[UUID] = None


@dataclass
class RiskAssessment:
    """Risk assessment for user or transaction."""
    overall_risk_score: float
    risk_level: str  # low, medium, high, critical
    risk_factors: Dict[str, float]
    temporal_risk: float
    behavioral_risk: float
    technical_risk: float
    contextual_risk: float
    assessment_timestamp: datetime
    confidence_interval: Tuple[float, float]


@dataclass
class FraudPattern:
    """Fraud pattern definition."""
    pattern_id: str
    pattern_name: str
    pattern_type: str
    detection_rules: List[Dict[str, Any]]
    weight: float
    threshold: float
    is_active: bool
    created_at: datetime


class FraudDetectionService:
    """
    Enterprise-grade fraud detection service with real-time analysis.
    
    Features:
    - Real-time fraud detection using ML models
    - Pattern recognition and anomaly detection
    - Risk scoring with multiple factors
    - Behavioral analysis and profiling
    - Technical fraud detection (IP, device, etc.)
    - Contextual risk assessment
    - High-performance processing with caching
    """
    
    def __init__(self):
        """Initialize fraud detection service with ML models."""
        self.isolation_forest = IsolationForest(
            n_estimators=100,
            contamination=0.1,
            random_state=42
        )
        self.scaler = StandardScaler()
        self.model_trained = False
        self._load_ml_models()
    
    def detect_fraud(self, event_data: Dict[str, Any], detection_context: Optional[Dict[str, Any]] = None) -> FraudDetectionResult:
        """
        Detect fraud in real-time using multiple detection methods.
        
        Detection methods:
        - Machine learning-based anomaly detection
        - Rule-based pattern matching
        - Behavioral analysis
        - Technical validation
        - Contextual risk assessment
        
        Performance optimizations:
        - Parallel processing of detection methods
        - Cached model predictions
        - Optimized database queries
        """
        try:
            # Security: Validate input data
            self._validate_event_data(event_data)
            
            # Performance: Get cached risk data
            cache_key = self._get_cache_key(event_data)
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result
            
            # Initialize detection result
            detection_result = FraudDetectionResult(
                is_fraudulent=False,
                risk_score=0.0,
                confidence_level=0.0,
                detected_patterns=[],
                risk_factors={},
                recommended_actions=[],
                detection_timestamp=timezone.now(),
                session_id=event_data.get('session_id'),
                user_id=event_data.get('user_id')
            )
            
            # Parallel fraud detection methods
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    'ml_detection': executor.submit(self._ml_detection, event_data),
                    'pattern_detection': executor.submit(self._pattern_detection, event_data),
                    'behavioral_analysis': executor.submit(self._behavioral_analysis, event_data),
                    'technical_validation': executor.submit(self._technical_validation, event_data)
                }
                
                # Collect results
                for method, future in futures.items():
                    try:
                        method_result = future.result(timeout=5)  # 5 second timeout
                        self._merge_detection_result(detection_result, method_result, method)
                    except Exception as e:
                        logger.error(f"Error in {method}: {str(e)}")
            
            # Calculate overall risk score
            detection_result.risk_score = self._calculate_overall_risk_score(detection_result.risk_factors)
            
            # Determine fraud status
            detection_result.is_fraudulent = detection_result.risk_score > 0.7
            detection_result.confidence_level = self._calculate_confidence_level(detection_result.risk_factors)
            
            # Generate recommendations
            detection_result.recommended_actions = self._generate_recommendations(detection_result)
            
            # Performance: Cache result
            cache.set(cache_key, detection_result, timeout=300)  # 5 minutes
            
            # Log detection for audit trail
            self._log_fraud_detection(detection_result, event_data)
            
            return detection_result
            
        except Exception as e:
            logger.error(f"Error in fraud detection: {str(e)}")
            return self._get_default_detection_result(event_data)
    
    def _ml_detection(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Machine learning-based fraud detection."""
        try:
            if not self.model_trained:
                return {'method': 'ml', 'risk_score': 0.0, 'patterns': [], 'confidence': 0.0}
            
            # Extract features for ML model
            features = self._extract_features(event_data)
            if not features:
                return {'method': 'ml', 'risk_score': 0.0, 'patterns': [], 'confidence': 0.0}
            
            # Scale features
            features_scaled = self.scaler.transform([features])
            
            # Predict fraud probability
            fraud_score = self.isolation_forest.decision_function(features_scaled)[0]
            fraud_probability = 1 / (1 + math.exp(-fraud_score))
            
            # Detect anomalies
            is_anomaly = self.isolation_forest.predict(features_scaled)[0] == -1
            
            return {
                'method': 'ml',
                'risk_score': float(fraud_probability),
                'is_anomaly': is_anomaly,
                'patterns': ['ml_anomaly'] if is_anomaly else [],
                'confidence': min(abs(fraud_score), 1.0)
            }
            
        except Exception as e:
            logger.error(f"Error in ML detection: {str(e)}")
            return {'method': 'ml', 'risk_score': 0.0, 'patterns': [], 'confidence': 0.0}
    
    def _pattern_detection(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Pattern-based fraud detection using predefined rules."""
        try:
            detected_patterns = []
            total_risk_score = 0.0
            
            # Get active fraud patterns
            active_patterns = self._get_active_fraud_patterns()
            
            for pattern in active_patterns:
                pattern_match = self._evaluate_pattern(pattern, event_data)
                if pattern_match['matches']:
                    detected_patterns.append(pattern.pattern_name)
                    total_risk_score += pattern_match['risk_score'] * pattern.weight
            
            return {
                'method': 'pattern',
                'risk_score': min(total_risk_score, 1.0),
                'patterns': detected_patterns,
                'confidence': min(len(detected_patterns) * 0.2, 1.0)
            }
            
        except Exception as e:
            logger.error(f"Error in pattern detection: {str(e)}")
            return {'method': 'pattern', 'risk_score': 0.0, 'patterns': [], 'confidence': 0.0}
    
    def _behavioral_analysis(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Behavioral analysis for fraud detection."""
        try:
            user_id = event_data.get('user_id')
            if not user_id:
                return {'method': 'behavioral', 'risk_score': 0.0, 'patterns': [], 'confidence': 0.0}
            
            # Get user behavior history
            behavior_history = self._get_user_behavior_history(user_id)
            
            # Analyze behavioral patterns
            risk_factors = {}
            
            # Frequency analysis
            frequency_risk = self._analyze_frequency(behavior_history, event_data)
            risk_factors['frequency'] = frequency_risk
            
            # Time pattern analysis
            time_risk = self._analyze_time_patterns(behavior_history, event_data)
            risk_factors['time_pattern'] = time_risk
            
            # Location analysis
            location_risk = self._analyze_location_patterns(behavior_history, event_data)
            risk_factors['location'] = location_risk
            
            # Device analysis
            device_risk = self._analyze_device_patterns(behavior_history, event_data)
            risk_factors['device'] = device_risk
            
            # Calculate overall behavioral risk
            overall_risk = sum(risk_factors.values()) / len(risk_factors)
            
            detected_patterns = [key for key, value in risk_factors.items() if value > 0.5]
            
            return {
                'method': 'behavioral',
                'risk_score': overall_risk,
                'risk_factors': risk_factors,
                'patterns': detected_patterns,
                'confidence': min(len(detected_patterns) * 0.25, 1.0)
            }
            
        except Exception as e:
            logger.error(f"Error in behavioral analysis: {str(e)}")
            return {'method': 'behavioral', 'risk_score': 0.0, 'patterns': [], 'confidence': 0.0}
    
    def _technical_validation(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Technical validation for fraud detection."""
        try:
            risk_factors = {}
            total_risk_score = 0.0
            detected_patterns = []
            
            # IP address validation
            ip_risk = self._validate_ip_address(event_data.get('ip_address'))
            risk_factors['ip_address'] = ip_risk
            if ip_risk > 0.5:
                detected_patterns.append('suspicious_ip')
                total_risk_score += ip_risk * 0.3
            
            # User agent validation
            ua_risk = self._validate_user_agent(event_data.get('user_agent'))
            risk_factors['user_agent'] = ua_risk
            if ua_risk > 0.5:
                detected_patterns.append('suspicious_user_agent')
                total_risk_score += ua_risk * 0.2
            
            # Device fingerprint validation
            device_risk = self._validate_device_fingerprint(event_data.get('device_fingerprint'))
            risk_factors['device'] = device_risk
            if device_risk > 0.5:
                detected_patterns.append('suspicious_device')
                total_risk_score += device_risk * 0.2
            
            # Geolocation validation
            geo_risk = self._validate_geolocation(event_data.get('ip_address'))
            risk_factors['geolocation'] = geo_risk
            if geo_risk > 0.5:
                detected_patterns.append('suspicious_location')
                total_risk_score += geo_risk * 0.3
            
            return {
                'method': 'technical',
                'risk_score': min(total_risk_score, 1.0),
                'risk_factors': risk_factors,
                'patterns': detected_patterns,
                'confidence': min(len(detected_patterns) * 0.3, 1.0)
            }
            
        except Exception as e:
            logger.error(f"Error in technical validation: {str(e)}")
            return {'method': 'technical', 'risk_score': 0.0, 'patterns': [], 'confidence': 0.0}
    
    def _extract_features(self, event_data: Dict[str, Any]) -> List[float]:
        """Extract features for ML model."""
        try:
            features = []
            
            # Temporal features
            event_time = event_data.get('timestamp', timezone.now())
            features.append(event_time.hour / 24.0)  # Hour of day
            features.append(event_time.weekday() / 7.0)  # Day of week
            
            # Frequency features
            user_id = event_data.get('user_id')
            if user_id:
                recent_events = self._get_recent_event_count(user_id, hours=24)
                features.append(min(recent_events / 100.0, 1.0))  # Normalized
            
            # Amount features
            amount = event_data.get('amount', 0)
            features.append(float(amount) / 10000.0)  # Normalized amount
            
            # Location features
            ip_address = event_data.get('ip_address')
            if ip_address:
                geo_data = self._get_geolocation_data(ip_address)
                features.append(geo_data.get('country_risk', 0.0))
                features.append(geo_data.get('proxy_risk', 0.0))
            
            # Device features
            device_fingerprint = event_data.get('device_fingerprint', '')
            features.append(len(device_fingerprint) / 100.0)  # Fingerprint length
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting features: {str(e)}")
            return []
    
    def _get_active_fraud_patterns(self) -> List[FraudPattern]:
        """Get active fraud patterns from database."""
        try:
            patterns = FraudPattern.objects.filter(is_active=True)
            return [
                FraudPattern(
                    pattern_id=str(p.id),
                    pattern_name=p.name,
                    pattern_type=p.pattern_type,
                    detection_rules=p.detection_rules,
                    weight=float(p.weight),
                    threshold=float(p.threshold),
                    is_active=p.is_active,
                    created_at=p.created_at
                )
                for p in patterns
            ]
        except Exception as e:
            logger.error(f"Error getting fraud patterns: {str(e)}")
            return []
    
    def _evaluate_pattern(self, pattern: FraudPattern, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate if event matches fraud pattern."""
        try:
            matches = False
            risk_score = 0.0
            
            for rule in pattern.detection_rules:
                if self._evaluate_rule(rule, event_data):
                    matches = True
                    risk_score += rule.get('risk_score', 0.5)
            
            return {
                'matches': matches,
                'risk_score': min(risk_score, 1.0)
            }
            
        except Exception as e:
            logger.error(f"Error evaluating pattern: {str(e)}")
            return {'matches': False, 'risk_score': 0.0}
    
    def _evaluate_rule(self, rule: Dict[str, Any], event_data: Dict[str, Any]) -> bool:
        """Evaluate individual fraud rule."""
        try:
            field = rule.get('field')
            operator = rule.get('operator')
            value = rule.get('value')
            event_value = event_data.get(field)
            
            if event_value is None:
                return False
            
            if operator == 'equals':
                return str(event_value) == str(value)
            elif operator == 'not_equals':
                return str(event_value) != str(value)
            elif operator == 'greater_than':
                return float(event_value) > float(value)
            elif operator == 'less_than':
                return float(event_value) < float(value)
            elif operator == 'contains':
                return str(value).lower() in str(event_value).lower()
            elif operator == 'regex':
                return bool(re.search(str(value), str(event_value), re.IGNORECASE))
            elif operator == 'in_range':
                min_val, max_val = value
                return min_val <= float(event_value) <= max_val
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error evaluating rule: {str(e)}")
            return False
    
    def _get_user_behavior_history(self, user_id: UUID) -> Dict[str, Any]:
        """Get user behavior history for analysis."""
        try:
            # Performance: Use optimized query with indexing
            recent_events = FraudDetection.objects.filter(
                user_id=user_id,
                created_at__gte=timezone.now() - timedelta(days=30)
            ).order_by('-created_at')[:1000]
            
            return {
                'total_events': recent_events.count(),
                'events_by_hour': self._group_events_by_hour(recent_events),
                'events_by_day': self._group_events_by_day(recent_events),
                'unique_ips': set(event.ip_address for event in recent_events if event.ip_address),
                'unique_devices': set(event.device_fingerprint for event in recent_events if event.device_fingerprint),
                'locations': self._extract_locations(recent_events)
            }
            
        except Exception as e:
            logger.error(f"Error getting user behavior history: {str(e)}")
            return {}
    
    def _analyze_frequency(self, behavior_history: Dict[str, Any], event_data: Dict[str, Any]) -> float:
        """Analyze frequency patterns for fraud detection."""
        try:
            total_events = behavior_history.get('total_events', 0)
            
            # High frequency risk
            if total_events > 1000:  # More than 1000 events in 30 days
                return min(total_events / 1000.0, 1.0)
            
            # Burst detection
            events_by_hour = behavior_history.get('events_by_hour', {})
            current_hour = timezone.now().hour
            current_hour_events = events_by_hour.get(current_hour, 0)
            
            if current_hour_events > 50:  # More than 50 events in current hour
                return min(current_hour_events / 50.0, 1.0)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error analyzing frequency: {str(e)}")
            return 0.0
    
    def _analyze_time_patterns(self, behavior_history: Dict[str, Any], event_data: Dict[str, Any]) -> float:
        """Analyze time patterns for fraud detection."""
        try:
            events_by_hour = behavior_history.get('events_by_hour', {})
            current_hour = timezone.now().hour
            
            # Unusual hour detection
            if current_hour < 6 or current_hour > 22:  # Late night activity
                typical_hours = sum(events_by_hour.get(h, 0) for h in range(6, 22))
                late_hours = sum(events_by_hour.get(h, 0) for h in [0, 1, 2, 3, 4, 5, 22, 23])
                
                if late_hours > typical_hours * 0.5:
                    return 0.7
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error analyzing time patterns: {str(e)}")
            return 0.0
    
    def _analyze_location_patterns(self, behavior_history: Dict[str, Any], event_data: Dict[str, Any]) -> float:
        """Analyze location patterns for fraud detection."""
        try:
            current_ip = event_data.get('ip_address')
            if not current_ip:
                return 0.0
            
            unique_ips = behavior_history.get('unique_ips', set())
            
            # New location detection
            if current_ip not in unique_ips and len(unique_ips) > 0:
                return 0.6
            
            # Multiple locations in short time
            recent_ips = self._get_recent_ips(event_data.get('user_id'), hours=1)
            if len(recent_ips) > 3:
                return 0.8
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error analyzing location patterns: {str(e)}")
            return 0.0
    
    def _analyze_device_patterns(self, behavior_history: Dict[str, Any], event_data: Dict[str, Any]) -> float:
        """Analyze device patterns for fraud detection."""
        try:
            current_device = event_data.get('device_fingerprint')
            if not current_device:
                return 0.0
            
            unique_devices = behavior_history.get('unique_devices', set())
            
            # New device detection
            if current_device not in unique_devices and len(unique_devices) > 0:
                return 0.5
            
            # Multiple devices in short time
            recent_devices = self._get_recent_devices(event_data.get('user_id'), hours=1)
            if len(recent_devices) > 2:
                return 0.7
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error analyzing device patterns: {str(e)}")
            return 0.0
    
    def _validate_ip_address(self, ip_address: Optional[str]) -> float:
        """Validate IP address for fraud detection."""
        try:
            if not ip_address:
                return 0.5  # Missing IP is suspicious
            
            # Check for private IPs
            if self._is_private_ip(ip_address):
                return 0.8
            
            # Check for known proxy/VPN
            if self._is_proxy_ip(ip_address):
                return 0.9
            
            # Check IP reputation
            reputation_score = self._get_ip_reputation(ip_address)
            return max(0.0, 1.0 - reputation_score)
            
        except Exception as e:
            logger.error(f"Error validating IP address: {str(e)}")
            return 0.5
    
    def _validate_user_agent(self, user_agent: Optional[str]) -> float:
        """Validate user agent for fraud detection."""
        try:
            if not user_agent:
                return 0.5  # Missing user agent is suspicious
            
            # Check for common bot patterns
            bot_patterns = [
                r'bot', r'crawler', r'spider', r'scraper',
                r'curl', r'wget', r'python', r'java'
            ]
            
            for pattern in bot_patterns:
                if re.search(pattern, user_agent, re.IGNORECASE):
                    return 0.9
            
            # Check for unusual user agents
            if len(user_agent) < 10 or len(user_agent) > 500:
                return 0.6
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error validating user agent: {str(e)}")
            return 0.5
    
    def _validate_device_fingerprint(self, device_fingerprint: Optional[str]) -> float:
        """Validate device fingerprint for fraud detection."""
        try:
            if not device_fingerprint:
                return 0.5  # Missing fingerprint is suspicious
            
            # Check for common patterns indicating automation
            automation_patterns = [
                'selenium', 'webdriver', 'phantomjs', 'headless'
            ]
            
            for pattern in automation_patterns:
                if pattern.lower() in device_fingerprint.lower():
                    return 0.9
            
            # Check fingerprint consistency
            if len(device_fingerprint) < 20 or len(device_fingerprint) > 1000:
                return 0.6
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error validating device fingerprint: {str(e)}")
            return 0.5
    
    def _validate_geolocation(self, ip_address: Optional[str]) -> float:
        """Validate geolocation for fraud detection."""
        try:
            if not ip_address:
                return 0.5
            
            geo_data = self._get_geolocation_data(ip_address)
            
            # Check for high-risk countries
            high_risk_countries = ['CN', 'RU', 'IR', 'KP']
            if geo_data.get('country_code') in high_risk_countries:
                return 0.7
            
            # Check for impossible locations
            if geo_data.get('is_proxy', False):
                return 0.8
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error validating geolocation: {str(e)}")
            return 0.5
    
    def _calculate_overall_risk_score(self, risk_factors: Dict[str, Any]) -> float:
        """Calculate overall risk score from individual factors."""
        try:
            if not risk_factors:
                return 0.0
            
            # Weight different detection methods
            weights = {
                'ml': 0.4,
                'pattern': 0.3,
                'behavioral': 0.2,
                'technical': 0.1
            }
            
            total_score = 0.0
            total_weight = 0.0
            
            for method, factors in risk_factors.items():
                if isinstance(factors, dict) and 'risk_score' in factors:
                    method_score = factors['risk_score']
                    method_weight = weights.get(method, 0.1)
                    total_score += method_score * method_weight
                    total_weight += method_weight
                elif isinstance(factors, (int, float)):
                    method_score = float(factors)
                    method_weight = weights.get(method, 0.1)
                    total_score += method_score * method_weight
                    total_weight += method_weight
            
            return min(total_score / total_weight if total_weight > 0 else 0.0, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating overall risk score: {str(e)}")
            return 0.0
    
    def _calculate_confidence_level(self, risk_factors: Dict[str, Any]) -> float:
        """Calculate confidence level in detection."""
        try:
            confidence_scores = []
            
            for method, factors in risk_factors.items():
                if isinstance(factors, dict) and 'confidence' in factors:
                    confidence_scores.append(factors['confidence'])
                elif isinstance(factors, (int, float)):
                    confidence_scores.append(min(abs(factors), 1.0))
            
            if not confidence_scores:
                return 0.0
            
            return sum(confidence_scores) / len(confidence_scores)
            
        except Exception as e:
            logger.error(f"Error calculating confidence level: {str(e)}")
            return 0.0
    
    def _generate_recommendations(self, detection_result: FraudDetectionResult) -> List[str]:
        """Generate recommendations based on detection results."""
        try:
            recommendations = []
            
            if detection_result.risk_score > 0.8:
                recommendations.extend([
                    'Block user immediately',
                    'Require manual review',
                    'Notify security team'
                ])
            elif detection_result.risk_score > 0.6:
                recommendations.extend([
                    'Require additional verification',
                    'Limit user access',
                    'Monitor closely'
                ])
            elif detection_result.risk_score > 0.4:
                recommendations.extend([
                    'Increase monitoring',
                    'Flag for review'
                ])
            
            # Pattern-specific recommendations
            if 'suspicious_ip' in detection_result.detected_patterns:
                recommendations.append('Block IP address')
            
            if 'suspicious_device' in detection_result.detected_patterns:
                recommendations.append('Block device fingerprint')
            
            if 'ml_anomaly' in detection_result.detected_patterns:
                recommendations.append('Investigate anomalous behavior')
            
            return list(set(recommendations))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            return ['Manual review recommended']
    
    def _merge_detection_result(self, detection_result: FraudDetectionResult, method_result: Dict[str, Any], method: str) -> None:
        """Merge detection result from specific method."""
        try:
            detection_result.risk_factors[method] = method_result
            
            if method_result.get('patterns'):
                detection_result.detected_patterns.extend(method_result['patterns'])
            
        except Exception as e:
            logger.error(f"Error merging detection result: {str(e)}")
    
    def _get_cache_key(self, event_data: Dict[str, Any]) -> str:
        """Generate cache key for event data."""
        try:
            user_id = event_data.get('user_id', 'anonymous')
            event_type = event_data.get('event_type', 'unknown')
            timestamp = event_data.get('timestamp', timezone.now())
            
            # Create hash for consistent cache key
            data_string = f"{user_id}_{event_type}_{timestamp.isoformat()}"
            return hashlib.md5(data_string.encode()).hexdigest()
            
        except Exception as e:
            logger.error(f"Error generating cache key: {str(e)}")
            return f"fraud_detection_{timezone.now().isoformat()}"
    
    def _validate_event_data(self, event_data: Dict[str, Any]) -> None:
        """Validate event data for security."""
        try:
            required_fields = ['event_type', 'timestamp']
            for field in required_fields:
                if field not in event_data:
                    raise AdvertiserValidationError(f"Required field missing: {field}")
            
            # Validate timestamp
            timestamp = event_data.get('timestamp')
            if isinstance(timestamp, str):
                try:
                    datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except ValueError:
                    raise AdvertiserValidationError("Invalid timestamp format")
            
        except Exception as e:
            logger.error(f"Error validating event data: {str(e)}")
            raise AdvertiserValidationError("Invalid event data format")
    
    def _get_default_detection_result(self, event_data: Dict[str, Any]) -> FraudDetectionResult:
        """Get default detection result for error cases."""
        return FraudDetectionResult(
            is_fraudulent=False,
            risk_score=0.0,
            confidence_level=0.0,
            detected_patterns=[],
            risk_factors={},
            recommended_actions=['Manual review required due to system error'],
            detection_timestamp=timezone.now(),
            session_id=event_data.get('session_id'),
            user_id=event_data.get('user_id')
        )
    
    def _log_fraud_detection(self, detection_result: FraudDetectionResult, event_data: Dict[str, Any]) -> None:
        """Log fraud detection for audit trail."""
        try:
            with transaction.atomic():
                FraudDetection.objects.create(
                    user_id=detection_result.user_id,
                    session_id=detection_result.session_id,
                    event_type=event_data.get('event_type'),
                    risk_score=detection_result.risk_score,
                    is_fraudulent=detection_result.is_fraudulent,
                    confidence_level=detection_result.confidence_level,
                    detected_patterns=detection_result.detected_patterns,
                    risk_factors=detection_result.risk_factors,
                    recommended_actions=detection_result.recommended_actions,
                    event_data=event_data,
                    detection_timestamp=detection_result.detection_timestamp
                )
                
        except Exception as e:
            logger.error(f"Error logging fraud detection: {str(e)}")
    
    def _load_ml_models(self) -> None:
        """Load pre-trained ML models."""
        try:
            # In production, this would load models from file storage
            # For now, we'll train with dummy data
            self._train_dummy_models()
            
        except Exception as e:
            logger.error(f"Error loading ML models: {str(e)}")
            self.model_trained = False
    
    def _train_dummy_models(self) -> None:
        """Train models with dummy data for demonstration."""
        try:
            # Generate dummy training data
            np.random.seed(42)
            n_samples = 1000
            n_features = 10
            
            X = np.random.randn(n_samples, n_features)
            
            # Train the model
            self.isolation_forest.fit(X)
            self.scaler.fit(X)
            self.model_trained = True
            
        except Exception as e:
            logger.error(f"Error training dummy models: {str(e)}")
            self.model_trained = False
    
    def _get_recent_event_count(self, user_id: UUID, hours: int = 24) -> int:
        """Get recent event count for user."""
        try:
            cutoff_time = timezone.now() - timedelta(hours=hours)
            return FraudDetection.objects.filter(
                user_id=user_id,
                detection_timestamp__gte=cutoff_time
            ).count()
        except Exception:
            return 0
    
    def _group_events_by_hour(self, events) -> Dict[int, int]:
        """Group events by hour of day."""
        try:
            hourly_counts = {}
            for event in events:
                hour = event.detection_timestamp.hour
                hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
            return hourly_counts
        except Exception:
            return {}
    
    def _group_events_by_day(self, events) -> Dict[int, int]:
        """Group events by day of week."""
        try:
            daily_counts = {}
            for event in events:
                day = event.detection_timestamp.weekday()
                daily_counts[day] = daily_counts.get(day, 0) + 1
            return daily_counts
        except Exception:
            return {}
    
    def _extract_locations(self, events) -> List[Dict[str, Any]]:
        """Extract location information from events."""
        try:
            locations = []
            for event in events:
                if event.ip_address:
                    geo_data = self._get_geolocation_data(event.ip_address)
                    locations.append({
                        'ip_address': event.ip_address,
                        'country_code': geo_data.get('country_code'),
                        'city': geo_data.get('city'),
                        'timestamp': event.detection_timestamp
                    })
            return locations
        except Exception:
            return []
    
    def _get_recent_ips(self, user_id: UUID, hours: int = 1) -> Set[str]:
        """Get recent IP addresses for user."""
        try:
            cutoff_time = timezone.now() - timedelta(hours=hours)
            recent_events = FraudDetection.objects.filter(
                user_id=user_id,
                detection_timestamp__gte=cutoff_time
            ).values('ip_address').distinct()
            
            return set(event['ip_address'] for event in recent_events if event['ip_address'])
        except Exception:
            return set()
    
    def _get_recent_devices(self, user_id: UUID, hours: int = 1) -> Set[str]:
        """Get recent device fingerprints for user."""
        try:
            cutoff_time = timezone.now() - timedelta(hours=hours)
            recent_events = FraudDetection.objects.filter(
                user_id=user_id,
                detection_timestamp__gte=cutoff_time
            ).values('device_fingerprint').distinct()
            
            return set(event['device_fingerprint'] for event in recent_events if event['device_fingerprint'])
        except Exception:
            return set()
    
    def _is_private_ip(self, ip_address: str) -> bool:
        """Check if IP address is private."""
        try:
            import ipaddress
            ip = ipaddress.ip_address(ip_address)
            return ip.is_private
        except Exception:
            return True  # Assume private if can't parse
    
    def _is_proxy_ip(self, ip_address: str) -> bool:
        """Check if IP address is a known proxy."""
        try:
            # In production, this would check against proxy databases
            # For now, basic heuristics
            proxy_indicators = ['tor', 'vpn', 'proxy']
            return any(indicator in ip_address.lower() for indicator in proxy_indicators)
        except Exception:
            return False
    
    def _get_ip_reputation(self, ip_address: str) -> float:
        """Get IP reputation score."""
        try:
            # In production, this would check IP reputation services
            # For now, return random score
            import random
            return random.uniform(0.3, 1.0)
        except Exception:
            return 0.5
    
    def _get_geolocation_data(self, ip_address: str) -> Dict[str, Any]:
        """Get geolocation data for IP address."""
        try:
            # In production, this would use GeoIP2 database
            # For now, return dummy data
            return {
                'country_code': 'US',
                'country_name': 'United States',
                'city': 'New York',
                'latitude': 40.7128,
                'longitude': -74.0060,
                'is_proxy': False,
                'country_risk': 0.1
            }
        except Exception:
            return {}


class RiskScoringService:
    """
    Enterprise-grade risk scoring service with comprehensive analysis.
    
    Features:
    - Multi-dimensional risk assessment
    - Dynamic risk scoring algorithms
    - Historical risk analysis
    - Contextual risk evaluation
    - Real-time risk updates
    """
    
    @staticmethod
    def calculate_risk_score(user_id: UUID, context: Optional[Dict[str, Any]] = None) -> RiskAssessment:
        """
        Calculate comprehensive risk score for user.
        
        Risk dimensions:
        - Temporal risk (time-based patterns)
        - Behavioral risk (user behavior patterns)
        - Technical risk (technical indicators)
        - Contextual risk (contextual factors)
        """
        try:
            # Initialize risk assessment
            assessment = RiskAssessment(
                overall_risk_score=0.0,
                risk_level='low',
                risk_factors={},
                temporal_risk=0.0,
                behavioral_risk=0.0,
                technical_risk=0.0,
                contextual_risk=0.0,
                assessment_timestamp=timezone.now(),
                confidence_interval=(0.0, 0.0)
            )
            
            # Calculate individual risk dimensions
            assessment.temporal_risk = RiskScoringService._calculate_temporal_risk(user_id, context)
            assessment.behavioral_risk = RiskScoringService._calculate_behavioral_risk(user_id, context)
            assessment.technical_risk = RiskScoringService._calculate_technical_risk(user_id, context)
            assessment.contextual_risk = RiskScoringService._calculate_contextual_risk(user_id, context)
            
            # Calculate overall risk score
            weights = {
                'temporal': 0.25,
                'behavioral': 0.35,
                'technical': 0.25,
                'contextual': 0.15
            }
            
            assessment.overall_risk_score = (
                assessment.temporal_risk * weights['temporal'] +
                assessment.behavioral_risk * weights['behavioral'] +
                assessment.technical_risk * weights['technical'] +
                assessment.contextual_risk * weights['contextual']
            )
            
            # Determine risk level
            assessment.risk_level = RiskScoringService._determine_risk_level(assessment.overall_risk_score)
            
            # Calculate confidence interval
            assessment.confidence_interval = RiskScoringService._calculate_confidence_interval(
                assessment.overall_risk_score, user_id
            )
            
            # Store risk assessment
            RiskScoringService._store_risk_assessment(user_id, assessment)
            
            return assessment
            
        except Exception as e:
            logger.error(f"Error calculating risk score: {str(e)}")
            return RiskScoringService._get_default_risk_assessment(user_id)
    
    @staticmethod
    def _calculate_temporal_risk(user_id: UUID, context: Optional[Dict[str, Any]]) -> float:
        """Calculate temporal risk based on time patterns."""
        try:
            # Get user's historical activity patterns
            historical_data = RiskScoringService._get_user_temporal_history(user_id)
            
            current_time = timezone.now()
            temporal_risk = 0.0
            
            # Unusual time of day
            current_hour = current_time.hour
            typical_hours = historical_data.get('typical_hours', set(range(9, 18)))  # 9 AM - 6 PM
            
            if current_hour not in typical_hours:
                temporal_risk += 0.3
            
            # Unusual day of week
            current_weekday = current_time.weekday()
            typical_weekdays = historical_data.get('typical_weekdays', set(range(0, 5)))  # Monday - Friday
            
            if current_weekday not in typical_weekdays:
                temporal_risk += 0.2
            
            # Recent activity frequency
            recent_activity = historical_data.get('recent_activity_count', 0)
            if recent_activity > 100:  # High frequency
                temporal_risk += 0.4
            
            return min(temporal_risk, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating temporal risk: {str(e)}")
            return 0.0
    
    @staticmethod
    def _calculate_behavioral_risk(user_id: UUID, context: Optional[Dict[str, Any]]) -> float:
        """Calculate behavioral risk based on user behavior."""
        try:
            # Get user's behavioral patterns
            behavioral_data = RiskScoringService._get_user_behavioral_history(user_id)
            
            behavioral_risk = 0.0
            
            # Unusual locations
            current_location = context.get('location') if context else None
            typical_locations = behavioral_data.get('typical_locations', set())
            
            if current_location and current_location not in typical_locations:
                behavioral_risk += 0.3
            
            # Unusual devices
            current_device = context.get('device') if context else None
            typical_devices = behavioral_data.get('typical_devices', set())
            
            if current_device and current_device not in typical_devices:
                behavioral_risk += 0.2
            
            # Rapid successive actions
            recent_actions = behavioral_data.get('recent_actions', [])
            if len(recent_actions) > 50 in timedelta(minutes=5):
                behavioral_risk += 0.5
            
            return min(behavioral_risk, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating behavioral risk: {str(e)}")
            return 0.0
    
    @staticmethod
    def _calculate_technical_risk(user_id: UUID, context: Optional[Dict[str, Any]]) -> float:
        """Calculate technical risk based on technical indicators."""
        try:
            technical_risk = 0.0
            
            if not context:
                return technical_risk
            
            # IP address risk
            ip_address = context.get('ip_address')
            if ip_address:
                if RiskScoringService._is_suspicious_ip(ip_address):
                    technical_risk += 0.4
            
            # User agent risk
            user_agent = context.get('user_agent')
            if user_agent:
                if RiskScoringService._is_suspicious_user_agent(user_agent):
                    technical_risk += 0.3
            
            # Device fingerprint risk
            device_fingerprint = context.get('device_fingerprint')
            if device_fingerprint:
                if RiskScoringService._is_suspicious_device(device_fingerprint):
                    technical_risk += 0.3
            
            return min(technical_risk, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating technical risk: {str(e)}")
            return 0.0
    
    @staticmethod
    def _calculate_contextual_risk(user_id: UUID, context: Optional[Dict[str, Any]]) -> float:
        """Calculate contextual risk based on contextual factors."""
        try:
            contextual_risk = 0.0
            
            if not context:
                return contextual_risk
            
            # Transaction amount risk
            amount = context.get('amount', 0)
            if amount > 10000:  # High amount
                contextual_risk += 0.3
            
            # New account risk
            account_age = RiskScoringService._get_account_age(user_id)
            if account_age.days < 7:  # New account
                contextual_risk += 0.4
            
            # Verification status risk
            verification_status = RiskScoringService._get_verification_status(user_id)
            if verification_status != 'verified':
                contextual_risk += 0.3
            
            return min(contextual_risk, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating contextual risk: {str(e)}")
            return 0.0
    
    @staticmethod
    def _determine_risk_level(risk_score: float) -> str:
        """Determine risk level based on risk score."""
        if risk_score >= 0.8:
            return 'critical'
        elif risk_score >= 0.6:
            return 'high'
        elif risk_score >= 0.4:
            return 'medium'
        else:
            return 'low'
    
    @staticmethod
    def _calculate_confidence_interval(risk_score: float, user_id: UUID) -> Tuple[float, float]:
        """Calculate confidence interval for risk score."""
        try:
            # Get historical risk scores for user
            historical_scores = RiskScoringService._get_historical_risk_scores(user_id)
            
            if len(historical_scores) < 2:
                return (max(0.0, risk_score - 0.1), min(1.0, risk_score + 0.1))
            
            # Calculate standard deviation
            import statistics
            std_dev = statistics.stdev(historical_scores)
            
            # 95% confidence interval
            margin = 1.96 * std_dev
            lower = max(0.0, risk_score - margin)
            upper = min(1.0, risk_score + margin)
            
            return (lower, upper)
            
        except Exception as e:
            logger.error(f"Error calculating confidence interval: {str(e)}")
            return (max(0.0, risk_score - 0.1), min(1.0, risk_score + 0.1))
    
    @staticmethod
    def _store_risk_assessment(user_id: UUID, assessment: RiskAssessment) -> None:
        """Store risk assessment in database."""
        try:
            with transaction.atomic():
                RiskScore.objects.create(
                    user_id=user_id,
                    overall_risk_score=assessment.overall_risk_score,
                    risk_level=assessment.risk_level,
                    risk_factors=assessment.risk_factors,
                    temporal_risk=assessment.temporal_risk,
                    behavioral_risk=assessment.behavioral_risk,
                    technical_risk=assessment.technical_risk,
                    contextual_risk=assessment.contextual_risk,
                    confidence_interval=assessment.confidence_interval,
                    assessment_timestamp=assessment.assessment_timestamp
                )
                
        except Exception as e:
            logger.error(f"Error storing risk assessment: {str(e)}")
    
    @staticmethod
    def _get_user_temporal_history(user_id: UUID) -> Dict[str, Any]:
        """Get user's temporal history."""
        try:
            # Performance: Use optimized query
            recent_events = FraudDetection.objects.filter(
                user_id=user_id,
                detection_timestamp__gte=timezone.now() - timedelta(days=30)
            ).order_by('-detection_timestamp')[:1000]
            
            # Extract temporal patterns
            hours = set()
            weekdays = set()
            recent_count = recent_events.count()
            
            for event in recent_events:
                hours.add(event.detection_timestamp.hour)
                weekdays.add(event.detection_timestamp.weekday())
            
            return {
                'typical_hours': hours,
                'typical_weekdays': weekdays,
                'recent_activity_count': recent_count
            }
            
        except Exception as e:
            logger.error(f"Error getting user temporal history: {str(e)}")
            return {}
    
    @staticmethod
    def _get_user_behavioral_history(user_id: UUID) -> Dict[str, Any]:
        """Get user's behavioral history."""
        try:
            # Performance: Use optimized query
            recent_events = FraudDetection.objects.filter(
                user_id=user_id,
                detection_timestamp__gte=timezone.now() - timedelta(days=30)
            ).order_by('-detection_timestamp')[:1000]
            
            # Extract behavioral patterns
            locations = set()
            devices = set()
            recent_actions = []
            
            for event in recent_events:
                if event.ip_address:
                    locations.add(event.ip_address)
                if event.device_fingerprint:
                    devices.add(event.device_fingerprint)
                
                recent_actions.append(event.detection_timestamp)
            
            return {
                'typical_locations': locations,
                'typical_devices': devices,
                'recent_actions': recent_actions
            }
            
        except Exception as e:
            logger.error(f"Error getting user behavioral history: {str(e)}")
            return {}
    
    @staticmethod
    def _get_account_age(user_id: UUID) -> timedelta:
        """Get account age."""
        try:
            from ..database_models.advertiser_model import Advertiser
            advertiser = Advertiser.objects.get(id=user_id)
            return timezone.now() - advertiser.created_at
        except Exception:
            return timedelta(days=365)  # Assume old account
    
    @staticmethod
    def _get_verification_status(user_id: UUID) -> str:
        """Get verification status."""
        try:
            from ..database_models.advertiser_model import Advertiser
            advertiser = Advertiser.objects.get(id=user_id)
            return 'verified' if advertiser.is_verified else 'unverified'
        except Exception:
            return 'unverified'
    
    @staticmethod
    def _get_historical_risk_scores(user_id: UUID) -> List[float]:
        """Get historical risk scores for user."""
        try:
            recent_scores = RiskScore.objects.filter(
                user_id=user_id
            ).order_by('-assessment_timestamp')[:50]
            
            return [score.overall_risk_score for score in recent_scores]
        except Exception:
            return []
    
    @staticmethod
    def _is_suspicious_ip(ip_address: str) -> bool:
        """Check if IP address is suspicious."""
        try:
            # Basic heuristics for suspicious IPs
            if not ip_address:
                return True
            
            # Check for private IPs
            import ipaddress
            try:
                ip = ipaddress.ip_address(ip_address)
                if ip.is_private:
                    return True
            except ValueError:
                return True
            
            # Check for known proxy patterns
            proxy_patterns = ['tor', 'vpn', 'proxy']
            return any(pattern in ip_address.lower() for pattern in proxy_patterns)
            
        except Exception:
            return True
    
    @staticmethod
    def _is_suspicious_user_agent(user_agent: str) -> bool:
        """Check if user agent is suspicious."""
        try:
            if not user_agent:
                return True
            
            # Check for bot patterns
            bot_patterns = [
                'bot', 'crawler', 'spider', 'scraper',
                'curl', 'wget', 'python', 'java'
            ]
            
            return any(pattern in user_agent.lower() for pattern in bot_patterns)
            
        except Exception:
            return True
    
    @staticmethod
    def _is_suspicious_device(device_fingerprint: str) -> bool:
        """Check if device fingerprint is suspicious."""
        try:
            if not device_fingerprint:
                return True
            
            # Check for automation indicators
            automation_patterns = [
                'selenium', 'webdriver', 'phantomjs', 'headless'
            ]
            
            return any(pattern in device_fingerprint.lower() for pattern in automation_patterns)
            
        except Exception:
            return True
    
    @staticmethod
    def _get_default_risk_assessment(user_id: UUID) -> RiskAssessment:
        """Get default risk assessment for error cases."""
        return RiskAssessment(
            overall_risk_score=0.5,
            risk_level='medium',
            risk_factors={},
            temporal_risk=0.0,
            behavioral_risk=0.0,
            technical_risk=0.0,
            contextual_risk=0.0,
            assessment_timestamp=timezone.now(),
            confidence_interval=(0.0, 1.0)
        )


class PatternAnalysisService:
    """
    Enterprise-grade pattern analysis service for fraud detection.
    
    Features:
    - Pattern recognition and learning
    - Anomaly detection in patterns
    - Dynamic pattern updates
    - Pattern classification
    - Performance optimization
    """
    
    @staticmethod
    def analyze_patterns(user_id: UUID, time_range: Optional[timedelta] = None) -> Dict[str, Any]:
        """Analyze patterns in user behavior."""
        try:
            if time_range is None:
                time_range = timedelta(days=30)
            
            # Get user's historical data
            historical_data = PatternAnalysisService._get_historical_data(user_id, time_range)
            
            # Analyze different pattern types
            temporal_patterns = PatternAnalysisService._analyze_temporal_patterns(historical_data)
            behavioral_patterns = PatternAnalysisService._analyze_behavioral_patterns(historical_data)
            technical_patterns = PatternAnalysisService._analyze_technical_patterns(historical_data)
            
            # Detect anomalies
            anomalies = PatternAnalysisService._detect_pattern_anomalies(historical_data)
            
            return {
                'user_id': str(user_id),
                'time_range_days': time_range.days,
                'temporal_patterns': temporal_patterns,
                'behavioral_patterns': behavioral_patterns,
                'technical_patterns': technical_patterns,
                'anomalies': anomalies,
                'analysis_timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing patterns: {str(e)}")
            return {'error': 'Failed to analyze patterns'}
    
    @staticmethod
    def _get_historical_data(user_id: UUID, time_range: timedelta) -> Dict[str, Any]:
        """Get historical data for pattern analysis."""
        try:
            cutoff_time = timezone.now() - time_range
            
            # Performance: Use optimized query with indexing
            events = FraudDetection.objects.filter(
                user_id=user_id,
                detection_timestamp__gte=cutoff_time
            ).order_by('detection_timestamp')
            
            return {
                'events': list(events),
                'total_events': events.count(),
                'date_range': {
                    'start': cutoff_time.isoformat(),
                    'end': timezone.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting historical data: {str(e)}")
            return {'events': [], 'total_events': 0}
    
    @staticmethod
    def _analyze_temporal_patterns(historical_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze temporal patterns."""
        try:
            events = historical_data.get('events', [])
            
            if not events:
                return {'patterns': [], 'insights': []}
            
            # Extract temporal features
            hourly_distribution = {}
            daily_distribution = {}
            weekly_distribution = {}
            
            for event in events:
                timestamp = event.detection_timestamp
                hour = timestamp.hour
                day = timestamp.day
                weekday = timestamp.weekday()
                
                hourly_distribution[hour] = hourly_distribution.get(hour, 0) + 1
                daily_distribution[day] = daily_distribution.get(day, 0) + 1
                weekly_distribution[weekday] = weekly_distribution.get(weekday, 0) + 1
            
            # Identify patterns
            patterns = []
            
            # Peak hours
            peak_hours = sorted(hourly_distribution.items(), key=lambda x: x[1], reverse=True)[:3]
            patterns.append({
                'type': 'peak_hours',
                'description': 'Most active hours',
                'data': [{'hour': h, 'count': c} for h, c in peak_hours]
            })
            
            # Peak days
            peak_days = sorted(daily_distribution.items(), key=lambda x: x[1], reverse=True)[:3]
            patterns.append({
                'type': 'peak_days',
                'description': 'Most active days',
                'data': [{'day': d, 'count': c} for d, c in peak_days]
            })
            
            # Weekday vs weekend pattern
            weekday_total = sum(weekly_distribution.get(d, 0) for d in range(5))
            weekend_total = sum(weekly_distribution.get(d, 0) for d in range(5, 7))
            
            patterns.append({
                'type': 'weekday_weekend_ratio',
                'description': 'Activity distribution between weekdays and weekends',
                'data': {
                    'weekday_total': weekday_total,
                    'weekend_total': weekend_total,
                    'weekday_percentage': weekday_total / (weekday_total + weekend_total) * 100 if (weekday_total + weekend_total) > 0 else 0,
                    'weekend_percentage': weekend_total / (weekday_total + weekend_total) * 100 if (weekday_total + weekend_total) > 0 else 0
                }
            })
            
            return {
                'patterns': patterns,
                'insights': PatternAnalysisService._generate_temporal_insights(patterns)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing temporal patterns: {str(e)}")
            return {'patterns': [], 'insights': []}
    
    @staticmethod
    def _analyze_behavioral_patterns(historical_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze behavioral patterns."""
        try:
            events = historical_data.get('events', [])
            
            if not events:
                return {'patterns': [], 'insights': []}
            
            # Extract behavioral features
            locations = {}
            devices = {}
            session_patterns = {}
            
            for event in events:
                # Location patterns
                location = event.ip_address
                if location:
                    locations[location] = locations.get(location, 0) + 1
                
                # Device patterns
                device = event.device_fingerprint
                if device:
                    devices[device] = devices.get(device, 0) + 1
                
                # Session patterns
                session_id = event.session_id
                if session_id:
                    if session_id not in session_patterns:
                        session_patterns[session_id] = {'count': 0, 'duration': 0}
                    session_patterns[session_id]['count'] += 1
            
            # Identify patterns
            patterns = []
            
            # Frequent locations
            top_locations = sorted(locations.items(), key=lambda x: x[1], reverse=True)[:5]
            patterns.append({
                'type': 'frequent_locations',
                'description': 'Most frequently used locations',
                'data': [{'location': loc, 'count': count} for loc, count in top_locations]
            })
            
            # Frequent devices
            top_devices = sorted(devices.items(), key=lambda x: x[1], reverse=True)[:5]
            patterns.append({
                'type': 'frequent_devices',
                'description': 'Most frequently used devices',
                'data': [{'device': dev, 'count': count} for dev, count in top_devices]
            })
            
            # Session patterns
            session_stats = {
                'total_sessions': len(session_patterns),
                'avg_events_per_session': sum(s['count'] for s in session_patterns.values()) / len(session_patterns) if session_patterns else 0
            }
            patterns.append({
                'type': 'session_patterns',
                'description': 'Session behavior patterns',
                'data': session_stats
            })
            
            return {
                'patterns': patterns,
                'insights': PatternAnalysisService._generate_behavioral_insights(patterns)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing behavioral patterns: {str(e)}")
            return {'patterns': [], 'insights': []}
    
    @staticmethod
    def _analyze_technical_patterns(historical_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze technical patterns."""
        try:
            events = historical_data.get('events', [])
            
            if not events:
                return {'patterns': [], 'insights': []}
            
            # Extract technical features
            user_agents = {}
            ip_risks = {}
            device_risks = {}
            
            for event in events:
                # User agent patterns
                ua = event.user_agent
                if ua:
                    user_agents[ua] = user_agents.get(ua, 0) + 1
                
                # IP risk patterns
                ip_risk = event.risk_factors.get('ip_address', 0) if event.risk_factors else 0
                ip_risks[ip_risk] = ip_risks.get(ip_risk, 0) + 1
                
                # Device risk patterns
                device_risk = event.risk_factors.get('device', 0) if event.risk_factors else 0
                device_risks[device_risk] = device_risks.get(device_risk, 0) + 1
            
            # Identify patterns
            patterns = []
            
            # User agent consistency
            top_user_agents = sorted(user_agents.items(), key=lambda x: x[1], reverse=True)[:3]
            patterns.append({
                'type': 'user_agent_consistency',
                'description': 'User agent usage patterns',
                'data': [{'user_agent': ua, 'count': count} for ua, count in top_user_agents]
            })
            
            # Risk distribution
            risk_distribution = {
                'ip_risks': dict(ip_risks),
                'device_risks': dict(device_risks)
            }
            patterns.append({
                'type': 'risk_distribution',
                'description': 'Risk factor distribution',
                'data': risk_distribution
            })
            
            return {
                'patterns': patterns,
                'insights': PatternAnalysisService._generate_technical_insights(patterns)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing technical patterns: {str(e)}")
            return {'patterns': [], 'insights': []}
    
    @staticmethod
    def _detect_pattern_anomalies(historical_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect anomalies in patterns."""
        try:
            events = historical_data.get('events', [])
            anomalies = []
            
            if len(events) < 10:
                return anomalies
            
            # Statistical anomaly detection
            risk_scores = [event.risk_score for event in events]
            
            if risk_scores:
                import statistics
                mean_risk = statistics.mean(risk_scores)
                std_risk = statistics.stdev(risk_scores)
                
                # Detect outliers (2 standard deviations from mean)
                threshold = mean_risk + 2 * std_risk
                
                for event in events:
                    if event.risk_score > threshold:
                        anomalies.append({
                            'type': 'statistical_outlier',
                            'event_id': str(event.id),
                            'risk_score': event.risk_score,
                            'threshold': threshold,
                            'timestamp': event.detection_timestamp.isoformat()
                        })
            
            return anomalies
            
        except Exception as e:
            logger.error(f"Error detecting pattern anomalies: {str(e)}")
            return []
    
    @staticmethod
    def _generate_temporal_insights(patterns: List[Dict[str, Any]]) -> List[str]:
        """Generate insights from temporal patterns."""
        insights = []
        
        for pattern in patterns:
            if pattern['type'] == 'peak_hours':
                peak_hour = pattern['data'][0]['hour']
                if peak_hour >= 22 or peak_hour <= 6:
                    insights.append("User shows high activity during late night hours")
            
            elif pattern['type'] == 'weekday_weekend_ratio':
                weekend_pct = pattern['data']['weekend_percentage']
                if weekend_pct > 60:
                    insights.append("User is more active on weekends than weekdays")
                elif weekend_pct < 20:
                    insights.append("User is primarily active on weekdays")
        
        return insights
    
    @staticmethod
    def _generate_behavioral_insights(patterns: List[Dict[str, Any]]) -> List[str]:
        """Generate insights from behavioral patterns."""
        insights = []
        
        for pattern in patterns:
            if pattern['type'] == 'frequent_locations':
                locations = pattern['data']
                if len(locations) == 1:
                    insights.append("User consistently uses the same location")
                elif len(locations) > 10:
                    insights.append("User shows high location diversity")
            
            elif pattern['type'] == 'frequent_devices':
                devices = pattern['data']
                if len(devices) == 1:
                    insights.append("User consistently uses the same device")
                elif len(devices) > 5:
                    insights.append("User shows high device diversity")
        
        return insights
    
    @staticmethod
    def _generate_technical_insights(patterns: List[Dict[str, Any]]) -> List[str]:
        """Generate insights from technical patterns."""
        insights = []
        
        for pattern in patterns:
            if pattern['type'] == 'user_agent_consistency':
                user_agents = pattern['data']
                if len(user_agents) == 1:
                    insights.append("User maintains consistent user agent")
                elif len(user_agents) > 10:
                    insights.append("User shows high user agent variability")
        
        return insights


class SecurityMonitoringService:
    """
    Enterprise-grade security monitoring service.
    
    Features:
    - Real-time security monitoring
    - Alert generation and management
    - Threat intelligence integration
    - Security incident tracking
    - Automated response actions
    """
    
    @staticmethod
    def create_security_alert(alert_data: Dict[str, Any], created_by: Optional[User] = None) -> SecurityAlert:
        """Create security alert with comprehensive validation."""
        try:
            # Validate alert data
            SecurityMonitoringService._validate_alert_data(alert_data)
            
            with transaction.atomic():
                # Create security alert
                alert = SecurityAlert.objects.create(
                    alert_type=alert_data.get('alert_type'),
                    severity=alert_data.get('severity', 'medium'),
                    title=alert_data.get('title'),
                    description=alert_data.get('description'),
                    user_id=alert_data.get('user_id'),
                    session_id=alert_data.get('session_id'),
                    ip_address=alert_data.get('ip_address'),
                    device_fingerprint=alert_data.get('device_fingerprint'),
                    threat_data=alert_data.get('threat_data', {}),
                    recommended_actions=alert_data.get('recommended_actions', []),
                    status='open',
                    created_at=timezone.now(),
                    created_by=created_by
                )
                
                # Send notification
                SecurityMonitoringService._send_security_notification(alert)
                
                # Log alert creation
                SecurityMonitoringService._log_security_alert(alert, created_by)
                
                return alert
                
        except Exception as e:
            logger.error(f"Error creating security alert: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create security alert: {str(e)}")
    
    @staticmethod
    def get_active_alerts(filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get active security alerts with filtering."""
        try:
            queryset = SecurityAlert.objects.filter(status='open')
            
            # Apply filters
            if filters:
                if 'severity' in filters:
                    queryset = queryset.filter(severity=filters['severity'])
                if 'alert_type' in filters:
                    queryset = queryset.filter(alert_type=filters['alert_type'])
                if 'date_from' in filters:
                    queryset = queryset.filter(created_at__date__gte=filters['date_from'])
                if 'date_to' in filters:
                    queryset = queryset.filter(created_at__date__lte=filters['date_to'])
            
            # Performance: Use select_related for optimization
            alerts = queryset.select_related('created_by').order_by('-created_at')
            
            return [
                {
                    'id': str(alert.id),
                    'alert_type': alert.alert_type,
                    'severity': alert.severity,
                    'title': alert.title,
                    'description': alert.description,
                    'user_id': str(alert.user_id) if alert.user_id else None,
                    'session_id': alert.session_id,
                    'ip_address': alert.ip_address,
                    'device_fingerprint': alert.device_fingerprint,
                    'threat_data': alert.threat_data,
                    'recommended_actions': alert.recommended_actions,
                    'status': alert.status,
                    'created_at': alert.created_at.isoformat(),
                    'created_by': alert.created_by.username if alert.created_by else None
                }
                for alert in alerts
            ]
            
        except Exception as e:
            logger.error(f"Error getting active alerts: {str(e)}")
            return []
    
    @staticmethod
    def update_alert_status(alert_id: UUID, status: str, updated_by: Optional[User] = None) -> bool:
        """Update security alert status."""
        try:
            with transaction.atomic():
                alert = SecurityAlert.objects.get(id=alert_id)
                alert.status = status
                alert.updated_at = timezone.now()
                alert.updated_by = updated_by
                alert.save(update_fields=['status', 'updated_at', 'updated_by'])
                
                # Log status update
                SecurityMonitoringService._log_alert_update(alert, status, updated_by)
                
                return True
                
        except SecurityAlert.DoesNotExist:
            logger.error(f"Security alert {alert_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error updating alert status: {str(e)}")
            return False
    
    @staticmethod
    def _validate_alert_data(alert_data: Dict[str, Any]) -> None:
        """Validate alert data."""
        required_fields = ['alert_type', 'title', 'description']
        for field in required_fields:
            if not alert_data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Validate alert type
        valid_types = ['fraud', 'suspicious_activity', 'security_breach', 'anomaly', 'threat']
        if alert_data.get('alert_type') not in valid_types:
            raise AdvertiserValidationError(f"Invalid alert type: {alert_data.get('alert_type')}")
        
        # Validate severity
        valid_severities = ['low', 'medium', 'high', 'critical']
        if alert_data.get('severity', 'medium') not in valid_severities:
            raise AdvertiserValidationError(f"Invalid severity: {alert_data.get('severity')}")
    
    @staticmethod
    def _send_security_notification(alert: SecurityAlert) -> None:
        """Send security notification."""
        try:
            # Create notification
            Notification.objects.create(
                user=alert.created_by,
                title=f'Security Alert: {alert.title}',
                message=alert.description,
                notification_type='security',
                priority='high' if alert.severity in ['high', 'critical'] else 'medium',
                channels=['in_app', 'email']
            )
            
            # Send email for high/critical alerts
            if alert.severity in ['high', 'critical']:
                send_mail(
                    subject=f'Security Alert: {alert.title}',
                    message=alert.description,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.SECURITY_TEAM_EMAIL],
                    fail_silently=False
                )
                
        except Exception as e:
            logger.error(f"Error sending security notification: {str(e)}")
    
    @staticmethod
    def _log_security_alert(alert: SecurityAlert, created_by: Optional[User]) -> None:
        """Log security alert for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_creation(
                alert,
                created_by,
                description=f"Created security alert: {alert.title}"
            )
        except Exception as e:
            logger.error(f"Error logging security alert: {str(e)}")
    
    @staticmethod
    def _log_alert_update(alert: SecurityAlert, status: str, updated_by: Optional[User]) -> None:
        """Log alert update for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_action(
                action='update_security_alert',
                object_type='SecurityAlert',
                object_id=str(alert.id),
                user=updated_by,
                description=f"Updated security alert status to: {status}"
            )
        except Exception as e:
            logger.error(f"Error logging alert update: {str(e)}")


class FraudPreventionService:
    """
    Main fraud prevention service that coordinates all fraud detection services.
    
    Features:
    - Unified fraud detection interface
    - Service coordination
    - Comprehensive fraud prevention
    - Real-time monitoring
    - Performance optimization
    """
    
    def __init__(self):
        """Initialize fraud prevention service."""
        self.detection_service = FraudDetectionService()
        self.risk_scoring_service = RiskScoringService()
        self.pattern_analysis_service = PatternAnalysisService()
        self.security_monitoring_service = SecurityMonitoringService()
    
    def comprehensive_fraud_analysis(self, event_data: Dict[str, Any], 
                                  context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform comprehensive fraud analysis."""
        try:
            # Initialize comprehensive result
            result = {
                'event_data': event_data,
                'context': context,
                'analysis_timestamp': timezone.now().isoformat(),
                'fraud_detection': None,
                'risk_assessment': None,
                'pattern_analysis': None,
                'security_alerts': [],
                'recommendations': []
            }
            
            # Perform fraud detection
            fraud_result = self.detection_service.detect_fraud(event_data, context)
            result['fraud_detection'] = {
                'is_fraudulent': fraud_result.is_fraudulent,
                'risk_score': fraud_result.risk_score,
                'confidence_level': fraud_result.confidence_level,
                'detected_patterns': fraud_result.detected_patterns,
                'risk_factors': fraud_result.risk_factors,
                'recommended_actions': fraud_result.recommended_actions
            }
            
            # Perform risk assessment
            if event_data.get('user_id'):
                risk_assessment = self.risk_scoring_service.calculate_risk_score(
                    event_data['user_id'], context
                )
                result['risk_assessment'] = {
                    'overall_risk_score': risk_assessment.overall_risk_score,
                    'risk_level': risk_assessment.risk_level,
                    'risk_factors': risk_assessment.risk_factors,
                    'temporal_risk': risk_assessment.temporal_risk,
                    'behavioral_risk': risk_assessment.behavioral_risk,
                    'technical_risk': risk_assessment.technical_risk,
                    'contextual_risk': risk_assessment.contextual_risk,
                    'confidence_interval': risk_assessment.confidence_interval
                }
            
            # Perform pattern analysis
            if event_data.get('user_id'):
                pattern_analysis = self.pattern_analysis_service.analyze_patterns(
                    event_data['user_id']
                )
                result['pattern_analysis'] = pattern_analysis
            
            # Generate security alerts if needed
            if fraud_result.is_fraudulent or fraud_result.risk_score > 0.7:
                alert_data = {
                    'alert_type': 'fraud',
                    'severity': 'high' if fraud_result.is_fraudulent else 'medium',
                    'title': 'Fraud Detection Alert',
                    'description': f'Fraud detected with risk score: {fraud_result.risk_score}',
                    'user_id': event_data.get('user_id'),
                    'session_id': event_data.get('session_id'),
                    'ip_address': event_data.get('ip_address'),
                    'device_fingerprint': event_data.get('device_fingerprint'),
                    'threat_data': fraud_result.risk_factors,
                    'recommended_actions': fraud_result.recommended_actions
                }
                
                try:
                    security_alert = self.security_monitoring_service.create_security_alert(alert_data)
                    result['security_alerts'].append({
                        'alert_id': str(security_alert.id),
                        'alert_type': security_alert.alert_type,
                        'severity': security_alert.severity,
                        'title': security_alert.title,
                        'created_at': security_alert.created_at.isoformat()
                    })
                except Exception as e:
                    logger.error(f"Error creating security alert: {str(e)}")
            
            # Generate comprehensive recommendations
            result['recommendations'] = self._generate_comprehensive_recommendations(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in comprehensive fraud analysis: {str(e)}")
            return {
                'error': 'Failed to perform comprehensive fraud analysis',
                'analysis_timestamp': timezone.now().isoformat()
            }
    
    def _generate_comprehensive_recommendations(self, analysis_result: Dict[str, Any]) -> List[str]:
        """Generate comprehensive recommendations."""
        try:
            recommendations = []
            
            fraud_detection = analysis_result.get('fraud_detection', {})
            risk_assessment = analysis_result.get('risk_assessment', {})
            
            # High-risk recommendations
            if fraud_detection.get('is_fraudulent'):
                recommendations.extend([
                    'Block user immediately',
                    'Flag all recent transactions',
                    'Require manual verification',
                    'Notify fraud investigation team'
                ])
            
            # Medium-risk recommendations
            elif fraud_detection.get('risk_score', 0) > 0.6:
                recommendations.extend([
                    'Increase monitoring',
                    'Require additional verification',
                    'Limit transaction amounts',
                    'Review recent activity'
                ])
            
            # Low-risk recommendations
            elif fraud_detection.get('risk_score', 0) > 0.3:
                recommendations.extend([
                    'Enhanced monitoring',
                    'Periodic review',
                    'Behavioral analysis'
                ])
            
            # Risk level specific recommendations
            risk_level = risk_assessment.get('risk_level', 'low')
            if risk_level == 'high':
                recommendations.append('Implement enhanced security measures')
            elif risk_level == 'critical':
                recommendations.append('Immediate security intervention required')
            
            return list(set(recommendations))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            return ['Manual review recommended']
