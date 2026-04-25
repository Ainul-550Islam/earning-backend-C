"""
Fraud Detection Service for Offer Routing System

This module provides comprehensive fraud detection capabilities,
including pattern recognition, anomaly detection, and real-time monitoring.
"""

import logging
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import get_user_model
from collections import defaultdict, deque

from ..models import RoutingDecisionLog, SecurityEvent, UserOfferHistory
from ..utils import get_client_ip, validate_ip_address

User = get_user_model()
logger = logging.getLogger(__name__)


class FraudDetectionService:
    """
    Comprehensive fraud detection service for offer routing.
    
    Detects various fraud patterns including:
    - Click fraud and bot activity
    - IP-based fraud
    - Device fingerprinting
    - Behavioral anomalies
    - Time-based patterns
    """
    
    def __init__(self):
        self.cache_timeout = 3600  # 1 hour
        self.max_history_size = 1000
        self.suspicious_thresholds = {
            'max_clicks_per_minute': 100,
            'max_conversions_per_hour': 50,
            'max_same_ip_concurrent': 10,
            'max_same_device_concurrent': 5,
            'conversion_rate_threshold': 0.5,  # 50%
            'time_pattern_threshold': 0.8
        }
    
    def analyze_user_activity(self, user_id: int, time_window: int = 3600) -> Dict[str, any]:
        """
        Analyze user activity for fraud patterns.
        
        Args:
            user_id: User ID to analyze
            time_window: Time window in seconds (default: 1 hour)
            
        Returns:
            Dictionary containing fraud analysis results
        """
        try:
            # Get recent activity
            cutoff_time = timezone.now() - timedelta(seconds=time_window)
            
            recent_decisions = RoutingDecisionLog.objects.filter(
                user_id=user_id,
                created_at__gte=cutoff_time
            ).order_by('-created_at')[:self.max_history_size]
            
            recent_conversions = UserOfferHistory.objects.filter(
                user_id=user_id,
                completed_at__gte=cutoff_time
            ).order_by('-completed_at')[:self.max_history_size]
            
            # Analyze patterns
            analysis = {
                'user_id': user_id,
                'time_window': time_window,
                'total_decisions': len(recent_decisions),
                'total_conversions': len(recent_conversions),
                'click_rate': self._calculate_click_rate(recent_decisions, time_window),
                'conversion_rate': self._calculate_conversion_rate(recent_conversions, time_window),
                'ip_diversity': self._analyze_ip_diversity(recent_decisions),
                'time_patterns': self._analyze_time_patterns(recent_decisions),
                'device_patterns': self._analyze_device_patterns(recent_decisions),
                'suspicious_indicators': self._detect_suspicious_indicators(recent_decisions, recent_conversions),
                'risk_score': 0
            }
            
            # Calculate risk score
            analysis['risk_score'] = self._calculate_risk_score(analysis)
            
            # Cache analysis
            cache_key = f"fraud_analysis:user_{user_id}:{time_window}"
            cache.set(cache_key, analysis, self.cache_timeout)
            
            logger.info(f"Fraud analysis completed for user {user_id}: risk_score={analysis['risk_score']}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in fraud analysis for user {user_id}: {e}")
            return {'error': str(e)}
    
    def detect_ip_fraud(self, ip_address: str, time_window: int = 3600) -> Dict[str, any]:
        """
        Detect IP-based fraud patterns.
        
        Args:
            ip_address: IP address to analyze
            time_window: Time window in seconds
            
        Returns:
            Dictionary containing IP fraud analysis
        """
        try:
            # Get recent activity from this IP
            cutoff_time = timezone.now() - timedelta(seconds=time_window)
            
            recent_decisions = RoutingDecisionLog.objects.filter(
                ip_address=ip_address,
                created_at__gte=cutoff_time
            ).order_by('-created_at')[:self.max_history_size]
            
            # Analyze IP patterns
            analysis = {
                'ip_address': ip_address,
                'time_window': time_window,
                'unique_users': len(set(d.user_id for d in recent_decisions)),
                'total_requests': len(recent_decisions),
                'requests_per_minute': len(recent_decisions) / (time_window / 60),
                'user_switching': self._detect_user_switching(recent_decisions),
                'concurrent_requests': self._detect_concurrent_requests(recent_decisions),
                'geographic_anomalies': self._detect_geographic_anomalies(recent_decisions),
                'risk_score': 0
            }
            
            # Calculate risk score
            analysis['risk_score'] = self._calculate_ip_risk_score(analysis)
            
            # Cache analysis
            cache_key = f"fraud_ip:{ip_address}:{time_window}"
            cache.set(cache_key, analysis, self.cache_timeout)
            
            logger.info(f"IP fraud analysis completed for {ip_address}: risk_score={analysis['risk_score']}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in IP fraud analysis for {ip_address}: {e}")
            return {'error': str(e)}
    
    def detect_device_fraud(self, device_fingerprint: str, time_window: int = 3600) -> Dict[str, any]:
        """
        Detect device-based fraud patterns.
        
        Args:
            device_fingerprint: Device fingerprint to analyze
            time_window: Time window in seconds
            
        Returns:
            Dictionary containing device fraud analysis
        """
        try:
            # Get recent activity from this device
            cutoff_time = timezone.now() - timedelta(seconds=time_window)
            
            recent_decisions = RoutingDecisionLog.objects.filter(
                device_fingerprint=device_fingerprint,
                created_at__gte=cutoff_time
            ).order_by('-created_at')[:self.max_history_size]
            
            # Analyze device patterns
            analysis = {
                'device_fingerprint': device_fingerprint,
                'time_window': time_window,
                'unique_users': len(set(d.user_id for d in recent_decisions)),
                'total_requests': len(recent_decisions),
                'requests_per_minute': len(recent_decisions) / (time_window / 60),
                'automated_behavior': self._detect_automated_behavior(recent_decisions),
                'unusual_timing': self._detect_unusual_timing(recent_decisions),
                'risk_score': 0
            }
            
            # Calculate risk score
            analysis['risk_score'] = self._calculate_device_risk_score(analysis)
            
            # Cache analysis
            cache_key = f"fraud_device:{device_fingerprint}:{time_window}"
            cache.set(cache_key, analysis, self.cache_timeout)
            
            logger.info(f"Device fraud analysis completed for {device_fingerprint}: risk_score={analysis['risk_score']}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in device fraud analysis for {device_fingerprint}: {e}")
            return {'error': str(e)}
    
    def detect_conversion_fraud(self, user_id: int, offer_id: int) -> Dict[str, any]:
        """
        Detect conversion fraud for specific user and offer.
        
        Args:
            user_id: User ID
            offer_id: Offer ID
            
        Returns:
            Dictionary containing conversion fraud analysis
        """
        try:
            # Get conversion history for this user and offer
            conversions = UserOfferHistory.objects.filter(
                user_id=user_id,
                offer_id=offer_id,
                completed_at__isnull=False
            ).order_by('-completed_at')
            
            if not conversions.exists():
                return {'user_id': user_id, 'offer_id': offer_id, 'conversions': 0}
            
            # Analyze conversion patterns
            analysis = {
                'user_id': user_id,
                'offer_id': offer_id,
                'total_conversions': conversions.count(),
                'conversion_times': [c.completed_at for c in conversions],
                'time_between_conversions': self._analyze_conversion_timing(conversions),
                'suspicious_patterns': self._detect_conversion_patterns(conversions),
                'risk_score': 0
            }
            
            # Calculate risk score
            analysis['risk_score'] = self._calculate_conversion_risk_score(analysis)
            
            logger.info(f"Conversion fraud analysis completed for user {user_id}, offer {offer_id}: risk_score={analysis['risk_score']}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in conversion fraud analysis for user {user_id}, offer {offer_id}: {e}")
            return {'error': str(e)}
    
    def _calculate_click_rate(self, decisions: List, time_window: int) -> float:
        """Calculate click rate per minute."""
        if not decisions:
            return 0.0
        
        return len(decisions) / (time_window / 60)
    
    def _calculate_conversion_rate(self, conversions: List, time_window: int) -> float:
        """Calculate conversion rate per hour."""
        if not conversions:
            return 0.0
        
        return len(conversions) / (time_window / 3600)
    
    def _analyze_ip_diversity(self, decisions: List) -> Dict[str, any]:
        """Analyze IP address diversity."""
        if not decisions:
            return {'unique_ips': 0, 'ip_concentration': 0.0}
        
        ip_counts = defaultdict(int)
        for decision in decisions:
            if hasattr(decision, 'ip_address'):
                ip_counts[decision.ip_address] += 1
        
        unique_ips = len(ip_counts)
        total_requests = len(decisions)
        ip_concentration = max(ip_counts.values()) / total_requests if total_requests > 0 else 0
        
        return {
            'unique_ips': unique_ips,
            'ip_concentration': ip_concentration,
            'suspicious': ip_concentration > 0.8  # 80% from same IP
        }
    
    def _analyze_time_patterns(self, decisions: List) -> Dict[str, any]:
        """Analyze time-based patterns for bot detection."""
        if not decisions:
            return {'regular_pattern': True, 'suspicious_timing': False}
        
        # Extract timestamps
        timestamps = [d.created_at for d in decisions if hasattr(d, 'created_at')]
        if len(timestamps) < 10:
            return {'regular_pattern': True, 'suspicious_timing': False}
        
        # Analyze intervals
        intervals = []
        for i in range(1, len(timestamps)):
            interval = (timestamps[i] - timestamps[i-1]).total_seconds()
            intervals.append(interval)
        
        if not intervals:
            return {'regular_pattern': True, 'suspicious_timing': False}
        
        # Calculate statistics
        avg_interval = sum(intervals) / len(intervals)
        variance = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)
        
        # Suspicious if too regular (bot-like) or too fast
        regular_pattern = variance < 1.0  # Less than 1 second variance
        suspicious_timing = avg_interval < 1.0  # Average less than 1 second
        
        return {
            'regular_pattern': regular_pattern,
            'suspicious_timing': suspicious_timing,
            'avg_interval': avg_interval,
            'variance': variance,
            'requests_per_second': 1 / avg_interval if avg_interval > 0 else 0
        }
    
    def _analyze_device_patterns(self, decisions: List) -> Dict[str, any]:
        """Analyze device patterns."""
        if not decisions:
            return {'unique_devices': 0, 'device_concentration': 0.0}
        
        device_counts = defaultdict(int)
        for decision in decisions:
            if hasattr(decision, 'device_fingerprint'):
                device_counts[decision.device_fingerprint] += 1
        
        unique_devices = len(device_counts)
        total_requests = len(decisions)
        device_concentration = max(device_counts.values()) / total_requests if total_requests > 0 else 0
        
        return {
            'unique_devices': unique_devices,
            'device_concentration': device_concentration,
            'suspicious': device_concentration > 0.9  # 90% from same device
        }
    
    def _detect_suspicious_indicators(self, decisions: List, conversions: List) -> List[str]:
        """Detect suspicious indicators."""
        indicators = []
        
        # High click rate
        click_rate = self._calculate_click_rate(decisions, 3600)  # 1 hour
        if click_rate > self.suspicious_thresholds['max_clicks_per_minute']:
            indicators.append('high_click_rate')
        
        # High conversion rate
        conversion_rate = self._calculate_conversion_rate(conversions, 3600)  # 1 hour
        if conversion_rate > self.suspicious_thresholds['max_conversions_per_hour']:
            indicators.append('high_conversion_rate')
        
        # Low conversion rate (potential click fraud)
        if conversion_rate > 0 and conversion_rate < 0.1:  # Less than 10%
            indicators.append('low_conversion_rate')
        
        # IP concentration
        ip_analysis = self._analyze_ip_diversity(decisions)
        if ip_analysis.get('suspicious'):
            indicators.append('ip_concentration')
        
        # Device concentration
        device_analysis = self._analyze_device_patterns(decisions)
        if device_analysis.get('suspicious'):
            indicators.append('device_concentration')
        
        # Time patterns
        time_analysis = self._analyze_time_patterns(decisions)
        if time_analysis.get('suspicious_timing'):
            indicators.append('automated_timing')
        
        # Unusual time patterns
        if time_analysis.get('regular_pattern') and click_rate > 50:  # Regular but high volume
            indicators.append('suspicious_volume')
        
        return indicators
    
    def _calculate_risk_score(self, analysis: Dict) -> float:
        """Calculate overall risk score."""
        risk_score = 0.0
        
        # Add points for suspicious indicators
        indicators = analysis.get('suspicious_indicators', [])
        
        if 'high_click_rate' in indicators:
            risk_score += 30
        
        if 'high_conversion_rate' in indicators:
            risk_score += 25
        
        if 'low_conversion_rate' in indicators:
            risk_score += 20
        
        if 'ip_concentration' in indicators:
            risk_score += 25
        
        if 'device_concentration' in indicators:
            risk_score += 20
        
        if 'automated_timing' in indicators:
            risk_score += 35
        
        if 'suspicious_volume' in indicators:
            risk_score += 15
        
        # Normalize to 0-100 scale
        return min(risk_score, 100.0)
    
    def _detect_user_switching(self, decisions: List) -> bool:
        """Detect if user is switching between multiple accounts."""
        if len(decisions) < 5:
            return False
        
        # Check for different user IDs from same IP
        ip_users = set()
        for decision in decisions[-10:]:  # Last 10 decisions
            if hasattr(decision, 'user_id'):
                ip_users.add(decision.user_id)
        
        return len(ip_users) > 3  # More than 3 users from same IP
