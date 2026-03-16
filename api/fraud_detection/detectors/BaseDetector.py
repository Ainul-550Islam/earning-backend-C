import abc
from typing import Dict, List, Any, Optional, Tuple
from django.conf import settings
from django.db import transaction
from django.utils import timezone
import logging
import hashlib
import json

logger = logging.getLogger(__name__)

class BaseDetector(abc.ABC):
    """
    Abstract base class for all fraud detectors
    Implements Template Method pattern
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.detector_name = self.__class__.__name__
        self.detected_fraud = False
        self.fraud_score = 0
        self.confidence = 0
        self.reasons = []
        self.warnings = []
        self.evidence = {}
        
    @abc.abstractmethod
    def detect(self, data: Dict) -> Dict:
        """
        Main detection method to be implemented by subclasses
        Returns detection results
        """
        pass
    
    @abc.abstractmethod
    def get_required_fields(self) -> List[str]:
        """
        Return list of required fields for detection
        """
        pass
    
    def validate_data(self, data: Dict) -> bool:
        """
        Validate input data has required fields
        """
        required_fields = self.get_required_fields()
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            logger.warning(f"Missing required fields for {self.detector_name}: {missing_fields}")
            return False
        
        return True
    
    def calculate_fraud_score(self, risk_factors: List[Dict]) -> int:
        """
        Calculate fraud score based on weighted risk factors
        """
        total_weight = 0
        weighted_score = 0
        
        for factor in risk_factors:
            weight = factor.get('weight', 10)
            score = factor.get('score', 0)
            weighted_score += score * weight
            total_weight += weight
        
        if total_weight > 0:
            return min(100, int(weighted_score / total_weight))
        return 0
    
    def calculate_confidence(self, evidence_count: int, evidence_strength: int) -> int:
        """
        Calculate confidence score based on evidence
        """
        base_confidence = min(evidence_count * 10, 60)
        strength_bonus = evidence_strength * 5
        return min(100, base_confidence + strength_bonus)
    
    def add_reason(self, reason: str, score_impact: int = 10):
        """
        Add detection reason with score impact
        """
        self.reasons.append(reason)
        self.fraud_score += score_impact
        self.fraud_score = min(100, self.fraud_score)
    
    def add_warning(self, warning: str):
        """
        Add warning message
        """
        self.warnings.append(warning)
    
    def add_evidence(self, key: str, value: Any):
        """
        Add evidence to detection results
        """
        self.evidence[key] = value
    
    def get_detection_hash(self, data: Dict) -> str:
        """
        Generate unique hash for detection session
        """
        detection_data = {
            'detector': self.detector_name,
            'data': data,
            'timestamp': timezone.now().isoformat()
        }
        
        detection_str = json.dumps(detection_data, sort_keys=True)
        return hashlib.sha256(detection_str.encode()).hexdigest()
    
    def should_trigger_action(self, threshold: int = 70) -> Tuple[bool, str]:
        """
        Determine if action should be triggered based on fraud score
        """
        if self.fraud_score >= 90:
            return True, 'critical_fraud'
        elif self.fraud_score >= threshold:
            return True, 'high_risk_fraud'
        elif self.fraud_score >= 50:
            return True, 'medium_risk_review'
        elif self.fraud_score >= 30:
            return True, 'low_risk_monitor'
        
        return False, 'no_action'
    
    def get_detection_result(self) -> Dict:
        """
        Return standardized detection result
        """
        should_act, action_type = self.should_trigger_action()
        
        return {
            'detector': self.detector_name,
            'is_fraud': self.detected_fraud,
            'fraud_score': self.fraud_score,
            'confidence': self.confidence,
            'reasons': self.reasons,
            'warnings': self.warnings,
            'evidence': self.evidence,
            'action_required': should_act,
            'action_type': action_type,
            'detected_at': timezone.now().isoformat(),
            'detection_hash': self.get_detection_hash(self.evidence)
        }
    
    def log_detection(self, user_id: int = None):
        """
        Log detection results
        """
        log_data = {
            'detector': self.detector_name,
            'user_id': user_id,
            'fraud_score': self.fraud_score,
            'detected_fraud': self.detected_fraud,
            'reasons': self.reasons,
            'evidence_count': len(self.evidence),
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info(f"Fraud Detection - {json.dumps(log_data)}")
    
    @classmethod
    def get_detector_config(cls) -> Dict:
        """
        Get detector configuration
        """
        return {
            'name': cls.__name__,
            'description': cls.__doc__ or '',
            'version': '1.0.0',
            'enabled': True,
            'priority': 5
        }
    
    def cleanup(self):
        """
        Cleanup resources after detection
        """
        self.evidence.clear()
        self.reasons.clear()
        self.warnings.clear()