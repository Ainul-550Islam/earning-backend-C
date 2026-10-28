# 🚀 Fraud Detection System - Extension Guide

> **"One Owner Per Task"** - এই guide অনুসরণ করলে **core fraud_detection code কখনো touch করতে হবে না।**

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Extension Points](#extension-points)
3. [Adding New Detectors](#adding-new-detectors)
4. [Creating Custom Rules](#creating-custom-rules)
5. [Extending Fraud Scoring](#extending-fraud-scoring)
6. [Adding New Integrations](#adding-new-integrations)
7. [Custom Alert Systems](#custom-alert-systems)
8. [Best Practices](#best-practices)
9. [Examples](#examples)

---

## 🏗️ Architecture Overview

```
api/fraud_detection/
├── core/                    # ❌ NEVER TOUCH - Core system
│   ├── models.py
│   ├── services.py
│   ├── repositories.py
│   └── encryption.py
├── extensions/               # ✅ YOUR EXTENSIONS GO HERE
│   ├── detectors/           # Custom fraud detectors
│   ├── rules/               # Custom fraud rules
│   ├── scoring/             # Custom scoring algorithms
│   ├── integrations/        # External integrations
│   └── alerts/              # Custom alert systems
├── config/                  # ✅ CONFIGURATION ONLY
│   ├── settings.py
│   └── constants.py
└── tests/                   # ✅ YOUR TESTS
    ├── unit/
    ├── integration/
    └── fixtures/
```

---

## 🔌 Extension Points

### 1. **Custom Detectors** (`extensions/detectors/`)
- নতুন fraud detection patterns implement করুন
- Core system এর সাথে integrate করুন বিনা modification ছাড়া

### 2. **Custom Rules** (`extensions/rules/`)
- Business-specific fraud rules define করুন
- Runtime configuration সমর্থন করে

### 3. **Custom Scoring** (`extensions/scoring/`)
- নতুন risk calculation algorithms
- Machine learning models integrate করুন

### 4. **External Integrations** (`extensions/integrations/`)
- Third-party fraud detection services
- External data sources

### 5. **Custom Alerts** (`extensions/alerts/`)
- Custom notification systems
- Alert routing and escalation

---

## 🔍 Adding New Detectors

### Step 1: Create Detector Interface

```python
# api/fraud_detection/extensions/detectors/custom_detector.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from decimal import Decimal

class BaseCustomDetector(ABC):
    """
    Base class for all custom fraud detectors.
    
    Never modify core detector classes - extend this instead.
    """
    
    @abstractmethod
    def get_detector_name(self) -> str:
        """Return unique detector name."""
        pass
    
    @abstractmethod
    def get_detector_version(self) -> str:
        """Return detector version."""
        pass
    
    @abstractmethod
    def detect(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform fraud detection.
        
        Args:
            context: Detection context with user, transaction, etc.
            
        Returns:
            Detection result with score and evidence
        """
        pass
    
    @abstractmethod
    def get_confidence_threshold(self) -> Decimal:
        """Return confidence threshold for this detector."""
        pass
```

### Step 2: Implement Your Detector

```python
# api/fraud_detection/extensions/detectors/vpn_detector.py
from typing import Dict, Any
from decimal import Decimal
import requests

from .custom_detector import BaseCustomDetector
from api.fraud_detection.encryption import encrypt_ip_address

class VPNDetector(BaseCustomDetector):
    """
    Custom VPN/Proxy detection using external IP intelligence.
    """
    
    def __init__(self):
        self.vpn_api_url = "https://api.vpncheck.com/v1/check"
        self.api_key = settings.VPN_DETECTION_API_KEY
    
    def get_detector_name(self) -> str:
        return "vpn_detector"
    
    def get_detector_version(self) -> str:
        return "1.0.0"
    
    def get_confidence_threshold(self) -> Decimal:
        return Decimal("0.8")
    
    def detect(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect if user is using VPN/Proxy.
        
        Args:
            context: {
                'user_id': int,
                'ip_address': str,
                'user_agent': str,
                'timestamp': datetime
            }
        """
        ip_address = context.get('ip_address')
        if not ip_address:
            return self._empty_result()
        
        try:
            # Check against VPN database
            vpn_result = self._check_vpn_database(ip_address)
            
            # Additional heuristics
            heuristic_result = self._apply_heuristics(context)
            
            # Combine results
            final_score = max(vpn_result['score'], heuristic_result['score'])
            evidence = vpn_result['evidence'] + heuristic_result['evidence']
            
            return {
                'detector': self.get_detector_name(),
                'version': self.get_detector_version(),
                'score': final_score,
                'confidence': min(final_score / self.get_confidence_threshold(), 1.0),
                'evidence': evidence,
                'is_suspicious': final_score >= float(self.get_confidence_threshold()),
                'metadata': {
                    'ip_address': encrypt_ip_address(ip_address),
                    'checked_at': timezone.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"VPN detector error: {e}")
            return self._empty_result()
    
    def _check_vpn_database(self, ip_address: str) -> Dict[str, Any]:
        """Check IP against VPN database."""
        try:
            response = requests.get(
                f"{self.vpn_api_url}",
                params={'ip': ip_address, 'key': self.api_key},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('is_vpn') or data.get('is_proxy'):
                    return {
                        'score': Decimal(str(data.get('risk_score', 0.9))),
                        'evidence': [
                            f"IP detected as {'VPN' if data.get('is_vpn') else 'Proxy'}",
                            f"Provider: {data.get('provider', 'Unknown')}",
                            f"Country: {data.get('country', 'Unknown')}"
                        ]
                    }
            
        except Exception as e:
            logger.error(f"VPN database check failed: {e}")
        
        return {'score': Decimal('0'), 'evidence': []}
    
    def _apply_heuristics(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply heuristic-based VPN detection."""
        score = Decimal('0')
        evidence = []
        
        user_agent = context.get('user_agent', '').lower()
        
        # Check for common VPN/proxy user agents
        vpn_indicators = ['vpn', 'proxy', 'tunnel', 'anonymous', 'hidemyass']
        if any(indicator in user_agent for indicator in vpn_indicators):
            score += Decimal('0.3')
            evidence.append("VPN/Proxy indicators in user agent")
        
        # Check for suspicious IP patterns
        ip_address = context.get('ip_address', '')
        if self._is_suspicious_ip_pattern(ip_address):
            score += Decimal('0.2')
            evidence.append("Suspicious IP address pattern")
        
        return {'score': score, 'evidence': evidence}
    
    def _is_suspicious_ip_pattern(self, ip_address: str) -> bool:
        """Check for suspicious IP patterns."""
        # Implementation for suspicious IP detection
        # This is a placeholder - implement actual logic
        return False
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty detection result."""
        return {
            'detector': self.get_detector_name(),
            'version': self.get_detector_version(),
            'score': Decimal('0'),
            'confidence': Decimal('0'),
            'evidence': [],
            'is_suspicious': False,
            'metadata': {}
        }
```

### Step 3: Register Your Detector

```python
# api/fraud_detection/extensions/detectors/__init__.py
from .vpn_detector import VPNDetector
from .device_detector import DeviceDetector
from .behavior_detector import BehaviorDetector

# Registry of all custom detectors
CUSTOM_DETECTORS = [
    VPNDetector(),
    DeviceDetector(),
    BehaviorDetector(),
]

def get_custom_detectors():
    """Get all registered custom detectors."""
    return CUSTOM_DETECTORS

def register_detector(detector_class):
    """Register a new custom detector."""
    CUSTOM_DETECTORS.append(detector_class())
    return detector_class
```

---

## 📋 Creating Custom Rules

### Step 1: Define Rule Interface

```python
# api/fraud_detection/extensions/rules/base_rule.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from decimal import Decimal

class BaseCustomRule(ABC):
    """
    Base class for custom fraud rules.
    """
    
    @abstractmethod
    def get_rule_name(self) -> str:
        """Return unique rule name."""
        pass
    
    @abstractmethod
    def get_rule_priority(self) -> int:
        """Return rule priority (higher = more important)."""
        pass
    
    @abstractmethod
    def evaluate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate rule against context.
        
        Args:
            context: Evaluation context
            
        Returns:
            Rule evaluation result
        """
        pass
    
    @abstractmethod
    def is_enabled(self) -> bool:
        """Check if rule is enabled."""
        pass
```

### Step 2: Implement Your Rule

```python
# api/fraud_detection/extensions/rules/velocity_rule.py
from typing import Dict, Any
from decimal import Decimal
from datetime import timedelta

from django.utils import timezone
from django.db.models import Count, Q

from .base_rule import BaseCustomRule
from api.fraud_detection.models import FraudAttempt

class VelocityRule(BaseCustomRule):
    """
    Custom rule for detecting high-velocity fraud patterns.
    """
    
    def get_rule_name(self) -> str:
        return "high_velocity_detection"
    
    def get_rule_priority(self) -> int:
        return 80  # High priority
    
    def is_enabled(self) -> bool:
        return getattr(settings, 'VELOCITY_RULE_ENABLED', True)
    
    def evaluate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate velocity patterns.
        
        Args:
            context: {
                'user_id': int,
                'action': str,
                'timestamp': datetime,
                'metadata': dict
            }
        """
        user_id = context.get('user_id')
        action = context.get('action')
        timestamp = context.get('timestamp', timezone.now())
        
        if not user_id or not action:
            return self._empty_result()
        
        try:
            # Check different time windows
            velocity_metrics = self._calculate_velocity_metrics(user_id, action, timestamp)
            
            # Evaluate against thresholds
            violations = self._check_thresholds(velocity_metrics)
            
            if violations:
                return {
                    'rule': self.get_rule_name(),
                    'priority': self.get_rule_priority(),
                    'triggered': True,
                    'violations': violations,
                    'metrics': velocity_metrics,
                    'risk_score': self._calculate_risk_score(violations),
                    'recommendation': self._get_recommendation(violations),
                    'evaluated_at': timestamp.isoformat()
                }
            
            return self._empty_result()
            
        except Exception as e:
            logger.error(f"Velocity rule evaluation failed: {e}")
            return self._empty_result()
    
    def _calculate_velocity_metrics(self, user_id: int, action: str, timestamp) -> Dict[str, Any]:
        """Calculate velocity metrics for different time windows."""
        metrics = {}
        
        # Define time windows
        windows = {
            '1_minute': timedelta(minutes=1),
            '5_minutes': timedelta(minutes=5),
            '15_minutes': timedelta(minutes=15),
            '1_hour': timedelta(hours=1),
            '24_hours': timedelta(hours=24),
        }
        
        for window_name, window_delta in windows.items():
            start_time = timestamp - window_delta
            
            count = FraudAttempt.objects.filter(
                user_id=user_id,
                attempt_type=action,
                created_at__gte=start_time,
                created_at__lte=timestamp
            ).count()
            
            metrics[window_name] = {
                'count': count,
                'rate': count / window_delta.total_seconds() * 3600,  # per hour
                'window_start': start_time.isoformat(),
                'window_end': timestamp.isoformat()
            }
        
        return metrics
    
    def _check_thresholds(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check metrics against configured thresholds."""
        violations = []
        
        thresholds = getattr(settings, 'VELOCITY_THRESHOLDS', {
            '1_minute': {'max_count': 5, 'max_rate': 300},
            '5_minutes': {'max_count': 20, 'max_rate': 240},
            '15_minutes': {'max_count': 50, 'max_rate': 200},
            '1_hour': {'max_count': 100, 'max_rate': 100},
            '24_hours': {'max_count': 500, 'max_rate': 20},
        })
        
        for window_name, metric in metrics.items():
            threshold = thresholds.get(window_name, {})
            
            # Check count threshold
            max_count = threshold.get('max_count')
            if max_count and metric['count'] > max_count:
                violations.append({
                    'type': 'count_violation',
                    'window': window_name,
                    'actual': metric['count'],
                    'threshold': max_count,
                    'severity': 'high' if metric['count'] > max_count * 2 else 'medium'
                })
            
            # Check rate threshold
            max_rate = threshold.get('max_rate')
            if max_rate and metric['rate'] > max_rate:
                violations.append({
                    'type': 'rate_violation',
                    'window': window_name,
                    'actual': round(metric['rate'], 2),
                    'threshold': max_rate,
                    'severity': 'high' if metric['rate'] > max_rate * 2 else 'medium'
                })
        
        return violations
    
    def _calculate_risk_score(self, violations: List[Dict[str, Any]]) -> Decimal:
        """Calculate risk score based on violations."""
        if not violations:
            return Decimal('0')
        
        base_score = Decimal('50')  # Base score for any violation
        
        # Add points for each violation
        for violation in violations:
            if violation['severity'] == 'high':
                base_score += Decimal('30')
            elif violation['severity'] == 'medium':
                base_score += Decimal('15')
        
        return min(base_score, Decimal('100'))
    
    def _get_recommendation(self, violations: List[Dict[str, Any]]) -> str:
        """Get recommendation based on violations."""
        high_violations = [v for v in violations if v['severity'] == 'high']
        
        if high_violations:
            return "Immediate action required - Block user activity"
        elif len(violations) > 2:
            return "Enhanced monitoring recommended"
        else:
            return "Standard monitoring sufficient"
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty evaluation result."""
        return {
            'rule': self.get_rule_name(),
            'priority': self.get_rule_priority(),
            'triggered': False,
            'violations': [],
            'metrics': {},
            'risk_score': Decimal('0'),
            'recommendation': 'No action needed',
            'evaluated_at': timezone.now().isoformat()
        }
```

---

## 🎯 Extending Fraud Scoring

### Step 1: Create Custom Scorer

```python
# api/fraud_detection/extensions/scoring/ml_scorer.py
from typing import Dict, Any, List
from decimal import Decimal
import numpy as np

from .base_scorer import BaseCustomScorer
from api.fraud_detection.extensions.detectors import get_custom_detectors
from api.fraud_detection.extensions.rules import get_custom_rules

class MLScorer(BaseCustomScorer):
    """
    Machine learning based fraud scoring.
    """
    
    def __init__(self):
        self.model = self._load_model()
        self.feature_extractor = self._load_feature_extractor()
    
    def get_scorer_name(self) -> str:
        return "ml_fraud_scorer"
    
    def get_scorer_version(self) -> str:
        return "2.1.0"
    
    def calculate_score(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate ML-based fraud score.
        
        Args:
            context: Scoring context
            
        Returns:
            ML scoring result
        """
        try:
            # Extract features
            features = self.feature_extractor.extract_features(context)
            
            # Get detector scores
            detector_scores = self._get_detector_scores(context)
            
            # Get rule violations
            rule_violations = self._get_rule_violations(context)
            
            # Combine all features
            combined_features = self._combine_features(features, detector_scores, rule_violations)
            
            # Predict using ML model
            ml_score = self.model.predict_proba([combined_features])[0][1]
            
            # Apply calibration
            calibrated_score = self._calibrate_score(ml_score, context)
            
            return {
                'scorer': self.get_scorer_name(),
                'version': self.get_scorer_version(),
                'raw_score': Decimal(str(ml_score)),
                'calibrated_score': calibrated_score,
                'confidence': self._calculate_confidence(combined_features),
                'features': {
                    'count': len(combined_features),
                    'top_features': self._get_top_features(combined_features),
                    'feature_importance': self._get_feature_importance()
                },
                'explanation': self._generate_explanation(calibrated_score, context),
                'recommendations': self._generate_recommendations(calibrated_score),
                'scored_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"ML scoring failed: {e}")
            return self._fallback_score(context)
    
    def _load_model(self):
        """Load trained ML model."""
        # Implementation for loading your ML model
        # This could be a pickle file, TensorFlow model, etc.
        pass
    
    def _load_feature_extractor(self):
        """Load feature extractor."""
        # Implementation for feature extraction
        pass
    
    def _get_detector_scores(self, context: Dict[str, Any]) -> List[Decimal]:
        """Get scores from all custom detectors."""
        scores = []
        
        for detector in get_custom_detectors():
            try:
                result = detector.detect(context)
                scores.append(Decimal(str(result['score'])))
            except Exception as e:
                logger.error(f"Detector {detector.get_detector_name()} failed: {e}")
        
        return scores
    
    def _get_rule_violations(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get violations from all custom rules."""
        violations = []
        
        for rule in get_custom_rules():
            try:
                result = rule.evaluate(context)
                if result.get('triggered'):
                    violations.append(result)
            except Exception as e:
                logger.error(f"Rule {rule.get_rule_name()} failed: {e}")
        
        return violations
    
    def _combine_features(self, features: List[float], 
                         detector_scores: List[Decimal],
                         rule_violations: List[Dict[str, Any]]) -> List[float]:
        """Combine all features into single vector."""
        # Implementation for feature combination
        pass
    
    def _calibrate_score(self, raw_score: float, context: Dict[str, Any]) -> Decimal:
        """Calibrate ML score based on context."""
        # Implementation for score calibration
        pass
    
    def _calculate_confidence(self, features: List[float]) -> Decimal:
        """Calculate prediction confidence."""
        # Implementation for confidence calculation
        pass
    
    def _get_top_features(self, features: List[float]) -> List[str]:
        """Get most important features."""
        # Implementation for feature importance
        pass
    
    def _get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance mapping."""
        # Implementation for feature importance
        pass
    
    def _generate_explanation(self, score: Decimal, context: Dict[str, Any]) -> str:
        """Generate human-readable explanation."""
        if score >= Decimal('0.8'):
            return "High fraud risk detected based on multiple indicators"
        elif score >= Decimal('0.6'):
            return "Moderate fraud risk - additional monitoring recommended"
        else:
            return "Low fraud risk - normal activity patterns"
    
    def _generate_recommendations(self, score: Decimal) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        if score >= Decimal('0.8'):
            recommendations.extend([
                "Block transaction immediately",
                "Flag user for manual review",
                "Enable enhanced monitoring"
            ])
        elif score >= Decimal('0.6'):
            recommendations.extend([
                "Request additional verification",
                "Delay transaction processing",
                "Log for future analysis"
            ])
        
        return recommendations
    
    def _fallback_score(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback scoring when ML fails."""
        return {
            'scorer': self.get_scorer_name(),
            'version': self.get_scorer_version(),
            'raw_score': Decimal('0.5'),
            'calibrated_score': Decimal('0.5'),
            'confidence': Decimal('0.1'),
            'features': {},
            'explanation': "ML scoring failed - using fallback",
            'recommendations': ["Manual review recommended"],
            'scored_at': timezone.now().isoformat()
        }
```

---

## 🔗 Adding New Integrations

### Step 1: Create Integration Interface

```python
# api/fraud_detection/extensions/integrations/base_integration.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseCustomIntegration(ABC):
    """
    Base class for external integrations.
    """
    
    @abstractmethod
    def get_integration_name(self) -> str:
        """Return integration name."""
        pass
    
    @abstractmethod
    def get_integration_version(self) -> str:
        """Return integration version."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if integration is available."""
        pass
    
    @abstractmethod
    def get_risk_data(self, identifier: str, data_type: str) -> Dict[str, Any]:
        """
        Get risk data from external source.
        
        Args:
            identifier: IP address, email, device ID, etc.
            data_type: Type of data requested
            
        Returns:
            Risk data from external source
        """
        pass
```

### Step 2: Implement Integration

```python
# api/fraud_detection/extensions/integrations/threat_intel.py
import requests
from typing import Dict, Any

from .base_integration import BaseCustomIntegration
from django.conf import settings

class ThreatIntelIntegration(BaseCustomIntegration):
    """
    Integration with external threat intelligence providers.
    """
    
    def __init__(self):
        self.api_url = settings.THREAT_INTEL_API_URL
        self.api_key = settings.THREAT_INTEL_API_KEY
        self.timeout = getattr(settings, 'THREAT_INTEL_TIMEOUT', 10)
    
    def get_integration_name(self) -> str:
        return "threat_intelligence"
    
    def get_integration_version(self) -> str:
        return "1.0.0"
    
    def is_available(self) -> bool:
        return bool(self.api_url and self.api_key)
    
    def get_risk_data(self, identifier: str, data_type: str) -> Dict[str, Any]:
        """
        Get threat intelligence data.
        
        Args:
            identifier: IP address, email, domain, etc.
            data_type: 'ip', 'email', 'domain', 'hash'
            
        Returns:
            Threat intelligence data
        """
        if not self.is_available():
            return self._empty_response()
        
        try:
            endpoint = f"{self.api_url}/{data_type}/{identifier}"
            
            response = requests.get(
                endpoint,
                headers={'Authorization': f'Bearer {self.api_key}'},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return self._format_response(data)
            else:
                logger.error(f"Threat intel API error: {response.status_code}")
                return self._empty_response()
                
        except Exception as e:
            logger.error(f"Threat intel integration failed: {e}")
            return self._empty_response()
    
    def _format_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format API response to standard format."""
        return {
            'source': self.get_integration_name(),
            'risk_score': Decimal(str(data.get('risk_score', 0))),
            'confidence': Decimal(str(data.get('confidence', 0))),
            'indicators': data.get('indicators', []),
            'first_seen': data.get('first_seen'),
            'last_seen': data.get('last_seen'),
            'threat_types': data.get('threat_types', []),
            'geolocation': data.get('geolocation', {}),
            'raw_data': data
        }
    
    def _empty_response(self) -> Dict[str, Any]:
        """Return empty response."""
        return {
            'source': self.get_integration_name(),
            'risk_score': Decimal('0'),
            'confidence': Decimal('0'),
            'indicators': [],
            'first_seen': None,
            'last_seen': None,
            'threat_types': [],
            'geolocation': {},
            'raw_data': {}
        }
```

---

## 🚨 Custom Alert Systems

### Step 1: Create Alert Interface

```python
# api/fraud_detection/extensions/alerts/base_alert.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseCustomAlert(ABC):
    """
    Base class for custom alert systems.
    """
    
    @abstractmethod
    def get_alert_name(self) -> str:
        """Return alert system name."""
        pass
    
    @abstractmethod
    def send_alert(self, alert_data: Dict[str, Any]) -> bool:
        """
        Send alert to external system.
        
        Args:
            alert_data: Alert data
            
        Returns:
            True if sent successfully
        """
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if alert system is configured."""
        pass
```

### Step 2: Implement Alert System

```python
# api/fraud_detection/extensions/alerts/slack_alerts.py
import json
import requests
from typing import Dict, Any

from .base_alert import BaseCustomAlert
from django.conf import settings

class SlackAlertSystem(BaseCustomAlert):
    """
    Custom Slack alert integration.
    """
    
    def __init__(self):
        self.webhook_url = settings.SLACK_FRAUD_WEBHOOK_URL
        self.channel = settings.SLACK_FRAUD_CHANNEL
        self.timeout = getattr(settings, 'SLACK_ALERT_TIMEOUT', 10)
    
    def get_alert_name(self) -> str:
        return "slack_alerts"
    
    def is_configured(self) -> bool:
        return bool(self.webhook_url)
    
    def send_alert(self, alert_data: Dict[str, Any]) -> bool:
        """
        Send fraud alert to Slack.
        
        Args:
            alert_data: {
                'severity': str,
                'title': str,
                'description': str,
                'user_id': int,
                'risk_score': float,
                'evidence': list,
                'timestamp': str
            }
        """
        if not self.is_configured():
            logger.error("Slack alerts not configured")
            return False
        
        try:
            payload = self._build_slack_payload(alert_data)
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                logger.info(f"Slack alert sent: {alert_data['title']}")
                return True
            else:
                logger.error(f"Slack alert failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Slack alert error: {e}")
            return False
    
    def _build_slack_payload(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build Slack message payload."""
        severity_colors = {
            'low': 'good',
            'medium': 'warning',
            'high': 'danger',
            'critical': '#ff0000'
        }
        
        color = severity_colors.get(alert_data.get('severity', 'medium'), 'warning')
        
        return {
            'channel': self.channel,
            'username': 'Fraud Detection Bot',
            'icon_emoji': ':warning:',
            'attachments': [
                {
                    'color': color,
                    'title': f"🚨 {alert_data['title']}",
                    'title_link': f"{settings.ADMIN_URL}/fraud-detection/alerts/",
                    'text': alert_data['description'],
                    'fields': [
                        {
                            'title': 'User ID',
                            'value': alert_data.get('user_id', 'Unknown'),
                            'short': True
                        },
                        {
                            'title': 'Risk Score',
                            'value': f"{alert_data.get('risk_score', 0):.1f}",
                            'short': True
                        },
                        {
                            'title': 'Severity',
                            'value': alert_data.get('severity', 'Unknown').upper(),
                            'short': True
                        },
                        {
                            'title': 'Timestamp',
                            'value': alert_data.get('timestamp', 'Unknown'),
                            'short': True
                        }
                    ],
                    'footer': 'Fraud Detection System',
                    'ts': alert_data.get('timestamp', timezone.now().timestamp())
                }
            ]
        }
```

---

## 📚 Best Practices

### ✅ DO's

1. **Always extend, never modify core**
   ```python
   # ✅ GOOD: Extend base classes
   class MyDetector(BaseCustomDetector):
       pass
   
   # ❌ BAD: Modify core detector
   class FraudDetector(BaseDetector):
       # Never modify core classes
   ```

2. **Use absolute imports**
   ```python
   # ✅ GOOD
   from api.fraud_detection.extensions.detectors import BaseCustomDetector
   from api.fraud_detection.models import FraudAttempt
   
   # ❌ BAD
   from .detectors import BaseCustomDetector
   from ..models import FraudAttempt
   ```

3. **Handle failures gracefully**
   ```python
   # ✅ GOOD
   try:
       result = external_api_call()
       return result
   except Exception as e:
       logger.error(f"External API failed: {e}")
       return fallback_result()
   ```

4. **Cache external API calls**
   ```python
   # ✅ GOOD
   from django.core.cache import cache
   
   def get_threat_data(ip_address):
       cache_key = f"threat_data_{ip_address}"
       result = cache.get(cache_key)
       
       if not result:
           result = external_api_call(ip_address)
           cache.set(cache_key, result, timeout=3600)
       
       return result
   ```

5. **Use configuration for thresholds**
   ```python
   # ✅ GOOD
   THRESHOLDS = getattr(settings, 'CUSTOM_DETECTOR_THRESHOLDS', {
       'high_risk': 0.8,
       'medium_risk': 0.6,
       'low_risk': 0.3
   })
   ```

### ❌ DON'Ts

1. **Never modify core models**
   ```python
   # ❌ BAD: Never do this
   class FraudAttempt(models.Model):
       # Don't add fields to core models
       custom_field = models.CharField(...)
   ```

2. **Don't hardcode configurations**
   ```python
   # ❌ BAD
   API_URL = "https://api.example.com"  # Don't hardcode
   
   # ✅ GOOD
   API_URL = settings.EXTERNAL_API_URL
   ```

3. **Don't ignore errors**
   ```python
   # ❌ BAD
   result = risky_operation()  # No error handling
   
   # ✅ GOOD
   try:
       result = risky_operation()
   except SpecificException as e:
       logger.error(f"Operation failed: {e}")
       return default_result()
   ```

4. **Don't make blocking calls in request cycle**
   ```python
   # ❌ BAD: Blocking call in view
   def my_view(request):
       result = slow_external_api_call()  # Blocks request
       return response
   
   # ✅ GOOD: Use background tasks
   from celery import shared_task
   
   @shared_task
   def process_external_data(data):
       return slow_external_api_call(data)
   ```

---

## 🎯 Examples

### Example 1: Complete Custom Detector

```python
# api/fraud_detection/extensions/detectors/geo_anomaly_detector.py
from typing import Dict, Any
from decimal import Decimal
import geoip2.database

from .custom_detector import BaseCustomDetector

class GeoAnomalyDetector(BaseCustomDetector):
    """
    Detect geographic anomalies in user behavior.
    """
    
    def __init__(self):
        self.geoip_db = geoip2.database.Reader(settings.GEOIP_DATABASE_PATH)
    
    def get_detector_name(self) -> str:
        return "geo_anomaly_detector"
    
    def get_detector_version(self) -> str:
        return "1.0.0"
    
    def get_confidence_threshold(self) -> Decimal:
        return Decimal("0.7")
    
    def detect(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Detect geographic anomalies."""
        ip_address = context.get('ip_address')
        user_id = context.get('user_id')
        
        if not ip_address or not user_id:
            return self._empty_result()
        
        try:
            # Get current location
            current_location = self._get_location(ip_address)
            
            # Get user's location history
            location_history = self._get_user_location_history(user_id)
            
            # Calculate anomaly score
            anomaly_score = self._calculate_anomaly_score(
                current_location, location_history
            )
            
            # Generate evidence
            evidence = self._generate_evidence(
                current_location, location_history, anomaly_score
            )
            
            return {
                'detector': self.get_detector_name(),
                'version': self.get_detector_version(),
                'score': anomaly_score,
                'confidence': min(anomaly_score / self.get_confidence_threshold(), 1.0),
                'evidence': evidence,
                'is_suspicious': anomaly_score >= float(self.get_confidence_threshold()),
                'metadata': {
                    'current_location': current_location,
                    'location_history_count': len(location_history),
                    'checked_at': timezone.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Geo anomaly detector error: {e}")
            return self._empty_result()
    
    def _get_location(self, ip_address: str) -> Dict[str, Any]:
        """Get location from IP address."""
        try:
            response = self.geoip_db.city(ip_address)
            return {
                'country': response.country.name,
                'country_code': response.country.iso_code,
                'city': response.city.name,
                'latitude': response.location.latitude,
                'longitude': response.location.longitude,
                'timezone': response.location.time_zone
            }
        except Exception:
            return {}
    
    def _get_user_location_history(self, user_id: int) -> List[Dict[str, Any]]:
        """Get user's location history."""
        # Implementation for getting location history
        # This would query user's previous IP addresses
        return []
    
    def _calculate_anomaly_score(self, current_location: Dict[str, Any], 
                                history: List[Dict[str, Any]]) -> Decimal:
        """Calculate geographic anomaly score."""
        if not history:
            return Decimal('0')  # No history, no anomaly
        
        # Implementation for anomaly calculation
        # Check for impossible travel times, country hopping, etc.
        return Decimal('0.5')
    
    def _generate_evidence(self, current_location: Dict[str, Any],
                          history: List[Dict[str, Any]], 
                          score: Decimal) -> List[str]:
        """Generate evidence for anomaly score."""
        evidence = []
        
        if score > Decimal('0.5'):
            evidence.append("Geographic anomaly detected")
        
        if current_location.get('country') != history[-1].get('country'):
            evidence.append(f"Country change: {history[-1].get('country')} → {current_location.get('country')}")
        
        return evidence
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty detection result."""
        return {
            'detector': self.get_detector_name(),
            'version': self.get_detector_version(),
            'score': Decimal('0'),
            'confidence': Decimal('0'),
            'evidence': [],
            'is_suspicious': False,
            'metadata': {}
        }
```

### Example 2: Integration Test

```python
# api/fraud_detection/tests/test_custom_detectors.py
import pytest
from decimal import Decimal

from api.fraud_detection.extensions.detectors.vpn_detector import VPNDetector
from api.fraud_detection.extensions.detectors.geo_anomaly_detector import GeoAnomalyDetector

class TestCustomDetectors:
    """Test suite for custom detectors."""
    
    def test_vpn_detector_normal_ip(self):
        """Test VPN detector with normal IP."""
        detector = VPNDetector()
        
        context = {
            'user_id': 123,
            'ip_address': '192.168.1.1',  # Normal IP
            'user_agent': 'Mozilla/5.0...',
            'timestamp': timezone.now()
        }
        
        result = detector.detect(context)
        
        assert result['detector'] == 'vpn_detector'
        assert result['score'] == Decimal('0')
        assert result['is_suspicious'] is False
    
    def test_vpn_detector_suspicious_ip(self):
        """Test VPN detector with suspicious IP."""
        detector = VPNDetector()
        
        context = {
            'user_id': 123,
            'ip_address': '1.2.3.4',  # Known VPN IP
            'user_agent': 'Mozilla/5.0...',
            'timestamp': timezone.now()
        }
        
        result = detector.detect(context)
        
        assert result['detector'] == 'vpn_detector'
        assert result['score'] > Decimal('0')
        assert len(result['evidence']) > 0
    
    def test_geo_anomaly_detector_no_history(self):
        """Test geo anomaly detector with no history."""
        detector = GeoAnomalyDetector()
        
        context = {
            'user_id': 123,
            'ip_address': '192.168.1.1',
            'timestamp': timezone.now()
        }
        
        result = detector.detect(context)
        
        assert result['detector'] == 'geo_anomaly_detector'
        assert result['score'] == Decimal('0')  # No history, no anomaly
```

---

## 🚀 Deployment Checklist

### Before Deployment:

- [ ] All extensions use absolute imports
- [ ] Configuration is externalized (settings.py)
- [ ] Error handling is comprehensive
- [ ] Logging is implemented
- [ ] Tests are written and passing
- [ ] Documentation is updated
- [ ] Performance testing completed
- [ ] Security review completed

### After Deployment:

- [ ] Monitor extension performance
- [ ] Check error logs regularly
- [ ] Validate integration with core system
- [ ] Update documentation with real-world usage
- [ ] Collect user feedback
- [ ] Plan for future enhancements

---

## 📞 Support

For questions about extending the fraud detection system:

1. **Check this guide first** - Most answers are here
2. **Review existing extensions** - Learn from implemented examples
3. **Use the test suite** - See how extensions should work
4. **Contact the core team** - Only for system-level issues

---

## 🎉 Conclusion

By following this guide, you can extend the fraud detection system without ever touching the core code. This ensures:

- **System Stability** - Core fraud detection remains reliable
- **Easy Upgrades** - Core system updates won't break your extensions
- **Clean Architecture** - Clear separation between core and custom code
- **Maintainability** - Easy to understand and maintain extensions
- **Testing** - Comprehensive test coverage for all extensions

Remember: **"One Owner Per Task"** - Your extensions are your responsibility, the core system is ours! 🚀
