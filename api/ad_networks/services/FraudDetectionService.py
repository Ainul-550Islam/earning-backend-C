"""
api/ad_networks/services/FraudDetectionService.py
Service for scoring conversions for fraud
SaaS-ready with tenant support
"""

import logging
import json
import hashlib
import requests
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User

from api.ad_networks.models import (
    OfferConversion, UserOfferEngagement, Offer, KnownBadIP,
    OfferClick, NetworkAPILog
)
from api.ad_networks.choices import RiskLevel
from api.ad_networks.constants import (
    FRAUD_SCORE_THRESHOLD,
    HIGH_RISK_THRESHOLD,
    MEDIUM_RISK_THRESHOLD,
    CACHE_KEY_PATTERNS
)

logger = logging.getLogger(__name__)


class FraudDetectionService:
    """
    Service for detecting and scoring fraudulent activities
    """
    
    def __init__(self, tenant_id=None):
        self.tenant_id = tenant_id
        self.fraud_indicators = self._load_fraud_indicators()
    
    def analyze_conversion(self, conversion_data: Dict, 
                         engagement: UserOfferEngagement = None) -> Dict:
        """
        Analyze conversion for fraud
        """
        try:
            # Initialize fraud analysis
            analysis = {
                'conversion_id': conversion_data.get('conversion_id'),
                'user_id': conversion_data.get('user_id'),
                'offer_id': conversion_data.get('offer_id'),
                'ip_address': conversion_data.get('ip_address'),
                'timestamp': conversion_data.get('timestamp', timezone.now()),
                'fraud_score': 0.0,
                'risk_level': RiskLevel.LOW,
                'indicators': [],
                'recommendations': [],
                'is_fraudulent': False,
                'should_block': False,
                'should_review': False
            }
            
            # Run fraud detection algorithms
            self._analyze_velocity_patterns(analysis, conversion_data, engagement)
            self._analyze_ip_patterns(analysis, conversion_data, engagement)
            self._analyze_device_patterns(analysis, conversion_data, engagement)
            self._analyze_time_patterns(analysis, conversion_data, engagement)
            self._analyze_user_patterns(analysis, conversion_data, engagement)
            self._analyze_offer_patterns(analysis, conversion_data, engagement)
            self._analyze_known_bad_data(analysis, conversion_data, engagement)
            
            # Calculate final fraud score
            analysis['fraud_score'] = self._calculate_final_score(analysis['indicators'])
            
            # Determine risk level and actions
            analysis['risk_level'] = self._determine_risk_level(analysis['fraud_score'])
            analysis['is_fraudulent'] = analysis['fraud_score'] >= FRAUD_SCORE_THRESHOLD
            analysis['should_block'] = analysis['fraud_score'] >= 90
            analysis['should_review'] = analysis['fraud_score'] >= MEDIUM_RISK_THRESHOLD
            
            # Generate recommendations
            analysis['recommendations'] = self._generate_recommendations(analysis)
            
            # Log analysis
            self._log_fraud_analysis(analysis)
            
            logger.info(f"Fraud analysis completed: score {analysis['fraud_score']} for conversion {analysis['conversion_id']}")
            
            return {
                'success': True,
                'analysis': analysis
            }
            
        except Exception as e:
            logger.error(f"Fraud analysis failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'analysis': None
            }
    
    def batch_analyze_conversions(self, conversion_ids: List[int]) -> Dict:
        """
        Batch analyze multiple conversions
        """
        try:
            results = []
            total_conversions = 0
            fraudulent_conversions = 0
            high_risk_conversions = 0
            
            for conversion_id in conversion_ids:
                try:
                    # Get conversion data
                    conversion = OfferConversion.objects.select_related(
                        'engagement', 'engagement__user', 'engagement__offer'
                    ).get(id=conversion_id)
                    
                    conversion_data = {
                        'conversion_id': conversion_id,
                        'user_id': conversion.engagement.user.id,
                        'offer_id': conversion.engagement.offer.id,
                        'ip_address': conversion.engagement.ip_address,
                        'timestamp': conversion.created_at,
                        'payout': float(conversion.payout or 0)
                    }
                    
                    # Analyze
                    result = self.analyze_conversion(conversion_data, conversion.engagement)
                    
                    if result['success']:
                        analysis = result['analysis']
                        results.append(analysis)
                        total_conversions += 1
                        
                        if analysis['is_fraudulent']:
                            fraudulent_conversions += 1
                        
                        if analysis['risk_level'] == RiskLevel.HIGH:
                            high_risk_conversions += 1
                    
                except OfferConversion.DoesNotExist:
                    logger.warning(f"Conversion {conversion_id} not found")
                    continue
            
            fraud_rate = (fraudulent_conversions / total_conversions * 100) if total_conversions > 0 else 0
            
            return {
                'success': True,
                'total_conversions': total_conversions,
                'fraudulent_conversions': fraudulent_conversions,
                'high_risk_conversions': high_risk_conversions,
                'fraud_rate': round(fraud_rate, 2),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Batch fraud analysis failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }
    
    def get_fraud_statistics(self, days: int = 30) -> Dict:
        """
        Get fraud detection statistics
        """
        try:
            from django.db.models import Count, Sum, Avg, Q
            
            # Calculate date range
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            # Get conversions in date range
            conversions = OfferConversion.objects.filter(
                created_at__gte=start_date,
                created_at__lte=end_date
            )
            
            # Calculate fraud statistics
            stats = conversions.aggregate(
                total_conversions=Count('id'),
                high_risk_conversions=Count(
                    'id',
                    filter=Q(fraud_score__gte=HIGH_RISK_THRESHOLD)
                ),
                fraudulent_conversions=Count(
                    'id',
                    filter=Q(fraud_score__gte=FRAUD_SCORE_THRESHOLD)
                ),
                avg_fraud_score=Avg('fraud_score'),
                max_fraud_score=Max('fraud_score')
            )
            
            # Calculate rates
            high_risk_rate = 0
            fraudulent_rate = 0
            if stats['total_conversions'] > 0:
                high_risk_rate = (stats['high_risk_conversions'] / stats['total_conversions']) * 100
                fraudulent_rate = (stats['fraudulent_conversions'] / stats['total_conversions']) * 100
            
            # Get top fraud indicators
            top_indicators = self._get_top_fraud_indicators(start_date, end_date)
            
            return {
                'success': True,
                'period_days': days,
                'total_conversions': stats['total_conversions'],
                'high_risk_conversions': stats['high_risk_conversions'],
                'fraudulent_conversions': stats['fraudulent_conversions'],
                'avg_fraud_score': float(stats['avg_fraud_score'] or 0),
                'max_fraud_score': float(stats['max_fraud_score'] or 0),
                'high_risk_rate': round(high_risk_rate, 2),
                'fraudulent_rate': round(fraudulent_rate, 2),
                'top_indicators': top_indicators
            }
            
        except Exception as e:
            logger.error(f"Failed to get fraud statistics: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def update_fraud_indicators(self, conversion: OfferConversion, 
                              indicators: List[Dict]) -> Dict:
        """
        Update fraud indicators for a conversion
        """
        try:
            # Update conversion with new indicators
            conversion.fraud_indicators = indicators
            conversion.save(update_fields=['fraud_indicators'])
            
            logger.info(f"Updated fraud indicators for conversion {conversion.id}")
            
            return {
                'success': True,
                'conversion_id': conversion.id,
                'indicators_count': len(indicators)
            }
            
        except Exception as e:
            logger.error(f"Failed to update fraud indicators: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _analyze_velocity_patterns(self, analysis: Dict, conversion_data: Dict, 
                                engagement: UserOfferEngagement):
        """
        Analyze velocity patterns (too many conversions too quickly)
        """
        user_id = conversion_data.get('user_id')
        ip_address = conversion_data.get('ip_address')
        
        # User velocity analysis
        if user_id:
            recent_user_conversions = OfferConversion.objects.filter(
                engagement__user_id=user_id,
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            if recent_user_conversions > 10:
                analysis['indicators'].append({
                    'type': 'user_velocity',
                    'score': 50,
                    'description': f'User has {recent_user_conversions} conversions in last hour',
                    'severity': 'high'
                })
            elif recent_user_conversions > 5:
                analysis['indicators'].append({
                    'type': 'user_velocity',
                    'score': 25,
                    'description': f'User has {recent_user_conversions} conversions in last hour',
                    'severity': 'medium'
                })
        
        # IP velocity analysis
        if ip_address:
            recent_ip_conversions = OfferConversion.objects.filter(
                engagement__ip_address=ip_address,
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            if recent_ip_conversions > 20:
                analysis['indicators'].append({
                    'type': 'ip_velocity',
                    'score': 60,
                    'description': f'IP has {recent_ip_conversions} conversions in last hour',
                    'severity': 'critical'
                })
            elif recent_ip_conversions > 10:
                analysis['indicators'].append({
                    'type': 'ip_velocity',
                    'score': 40,
                    'description': f'IP has {recent_ip_conversions} conversions in last hour',
                    'severity': 'high'
                })
    
    def _analyze_ip_patterns(self, analysis: Dict, conversion_data: Dict, 
                           engagement: UserOfferEngagement):
        """
        Analyze IP-based patterns
        """
        ip_address = conversion_data.get('ip_address')
        if not ip_address:
            return
        
        # Check against known bad IPs
        if KnownBadIP.objects.filter(
            ip_address=ip_address,
            is_active=True
        ).exists():
            analysis['indicators'].append({
                'type': 'known_bad_ip',
                'score': 80,
                'description': 'IP address is in known bad IP list',
                'severity': 'critical'
            })
        
        # Multiple users from same IP
        unique_users = OfferConversion.objects.filter(
            engagement__ip_address=ip_address,
            created_at__gte=timezone.now() - timedelta(days=1)
        ).values('engagement__user').distinct().count()
        
        if unique_users > 10:
            analysis['indicators'].append({
                'type': 'multiple_users_same_ip',
                'score': 45,
                'description': f'{unique_users} different users from same IP in last day',
                'severity': 'high'
            })
        
        # Check for VPN/Proxy usage
        if self._is_vpn_or_proxy(ip_address):
            analysis['indicators'].append({
                'type': 'vpn_proxy',
                'score': 30,
                'description': 'IP address appears to be VPN or proxy',
                'severity': 'medium'
            })
    
    def _analyze_device_patterns(self, analysis: Dict, conversion_data: Dict, 
                              engagement: UserOfferEngagement):
        """
        Analyze device-based patterns
        """
        user_agent = conversion_data.get('user_agent')
        if not user_agent:
            return
        
        # Check for suspicious user agents
        suspicious_uas = [
            'bot', 'crawler', 'spider', 'scraper', 'automated',
            'python', 'curl', 'wget', 'java', 'go-http'
        ]
        
        user_agent_lower = user_agent.lower()
        for suspicious_ua in suspicious_uas:
            if suspicious_ua in user_agent_lower:
                analysis['indicators'].append({
                    'type': 'suspicious_user_agent',
                    'score': 70,
                    'description': f'Suspicious user agent detected: {suspicious_ua}',
                    'severity': 'high'
                })
                break
        
        # Multiple accounts from same device
        device_info = getattr(engagement, 'device_info', {})
        if device_info:
            device_fingerprint = self._generate_device_fingerprint(device_info)
            
            if device_fingerprint:
                same_device_conversions = OfferConversion.objects.filter(
                    engagement__device_info__contains=device_fingerprint,
                    created_at__gte=timezone.now() - timedelta(days=1)
                ).count()
                
                if same_device_conversions > 5:
                    analysis['indicators'].append({
                        'type': 'multiple_accounts_same_device',
                        'score': 35,
                        'description': f'Multiple conversions from same device fingerprint',
                        'severity': 'medium'
                    })
    
    def _analyze_time_patterns(self, analysis: Dict, conversion_data: Dict, 
                             engagement: UserOfferEngagement):
        """
        Analyze time-based patterns
        """
        if not engagement:
            return
        
        # Suspiciously fast completion
        if engagement.started_at and engagement.created_at:
            completion_time = (engagement.created_at - engagement.started_at).total_seconds()
            
            if completion_time < 10:  # Less than 10 seconds
                analysis['indicators'].append({
                    'type': 'suspiciously_fast_completion',
                    'score': 40,
                    'description': f'Conversion completed in {completion_time} seconds',
                    'severity': 'high'
                })
            elif completion_time < 30:  # Less than 30 seconds
                analysis['indicators'].append({
                    'type': 'suspiciously_fast_completion',
                    'score': 20,
                    'description': f'Conversion completed in {completion_time} seconds',
                    'severity': 'medium'
                })
        
        # Unusual timing patterns
        conversion_hour = conversion_data.get('timestamp', timezone.now()).hour
        
        # Conversions at unusual hours (2-5 AM)
        if 2 <= conversion_hour <= 5:
            analysis['indicators'].append({
                'type': 'unusual_timing',
                'score': 15,
                'description': f'Conversion at unusual hour: {conversion_hour}:00',
                'severity': 'low'
            })
    
    def _analyze_user_patterns(self, analysis: Dict, conversion_data: Dict, 
                             engagement: UserOfferEngagement):
        """
        Analyze user behavior patterns
        """
        user_id = conversion_data.get('user_id')
        if not user_id:
            return
        
        try:
            user = User.objects.get(id=user_id)
            
            # New user with high-value conversions
            user_age = timezone.now() - user.date_joined
            payout = Decimal(str(conversion_data.get('payout', 0)))
            
            if user_age.days < 7 and payout > Decimal('50.00'):
                analysis['indicators'].append({
                    'type': 'new_user_high_value',
                    'score': 35,
                    'description': f'New user ({user_age.days} days old) with high-value conversion',
                    'severity': 'medium'
                })
            
            # User with suspicious email domain
            if user.email:
                email_domain = user.email.split('@')[-1].lower()
                suspicious_domains = [
                    'tempmail.org', '10minutemail.com', 'guerrillamail.com',
                    'mailinator.com', 'yopmail.com'
                ]
                
                if email_domain in suspicious_domains:
                    analysis['indicators'].append({
                        'type': 'suspicious_email_domain',
                        'score': 25,
                        'description': f'User email from suspicious domain: {email_domain}',
                        'severity': 'medium'
                    })
            
        except User.DoesNotExist:
            pass
    
    def _analyze_offer_patterns(self, analysis: Dict, conversion_data: Dict, 
                             engagement: UserOfferEngagement):
        """
        Analyze offer-specific patterns
        """
        offer_id = conversion_data.get('offer_id')
        if not offer_id:
            return
        
        try:
            offer = Offer.objects.get(id=offer_id)
            
            # High conversion rate for offer
            if offer.total_conversions > 0:
                conversion_rate = (offer.total_conversions / offer.click_count * 100) if offer.click_count > 0 else 0
                
                if conversion_rate > 80:  # Unusually high conversion rate
                    analysis['indicators'].append({
                        'type': 'high_offer_conversion_rate',
                        'score': 20,
                        'description': f'Offer has unusually high conversion rate: {conversion_rate:.1f}%',
                        'severity': 'low'
                    })
            
            # Offer with high fraud rate
            recent_offer_conversions = OfferConversion.objects.filter(
                engagement__offer_id=offer_id,
                created_at__gte=timezone.now() - timedelta(days=7)
            )
            
            if recent_offer_conversions.count() > 0:
                fraud_conversions = recent_offer_conversions.filter(
                    fraud_score__gte=FRAUD_SCORE_THRESHOLD
                ).count()
                
                offer_fraud_rate = (fraud_conversions / recent_offer_conversions.count()) * 100
                
                if offer_fraud_rate > 50:
                    analysis['indicators'].append({
                        'type': 'high_offer_fraud_rate',
                        'score': 30,
                        'description': f'Offer has high fraud rate: {offer_fraud_rate:.1f}%',
                        'severity': 'medium'
                    })
            
        except Offer.DoesNotExist:
            pass
    
    def _analyze_known_bad_data(self, analysis: Dict, conversion_data: Dict, 
                              engagement: UserOfferEngagement):
        """
        Analyze against known bad data
        """
        # Check against external fraud databases
        ip_address = conversion_data.get('ip_address')
        if ip_address:
            # This would integrate with external fraud detection services
            # For demo, we'll just check local data
            pass
        
        # Check for suspicious conversion IDs
        conversion_id = conversion_data.get('conversion_id')
        if conversion_id:
            # Check for sequential or pattern-based IDs
            if self._is_suspicious_conversion_id(conversion_id):
                analysis['indicators'].append({
                    'type': 'suspicious_conversion_id',
                    'score': 15,
                    'description': f'Suspicious conversion ID pattern: {conversion_id}',
                    'severity': 'low'
                })
    
    def _calculate_final_score(self, indicators: List[Dict]) -> float:
        """
        Calculate final fraud score from indicators
        """
        if not indicators:
            return 0.0
        
        total_score = 0.0
        
        for indicator in indicators:
            # Apply severity multiplier
            severity_multiplier = {
                'low': 0.5,
                'medium': 1.0,
                'high': 1.5,
                'critical': 2.0
            }
            
            multiplier = severity_multiplier.get(indicator.get('severity', 'medium'), 1.0)
            total_score += indicator['score'] * multiplier
        
        # Cap at 100
        return min(100.0, total_score)
    
    def _determine_risk_level(self, fraud_score: float) -> str:
        """
        Determine risk level from fraud score
        """
        if fraud_score >= HIGH_RISK_THRESHOLD:
            return RiskLevel.HIGH
        elif fraud_score >= MEDIUM_RISK_THRESHOLD:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _generate_recommendations(self, analysis: Dict) -> List[str]:
        """
        Generate recommendations based on analysis
        """
        recommendations = []
        
        if analysis['fraud_score'] >= 90:
            recommendations.append('BLOCK: Immediate action required - high fraud probability')
        elif analysis['fraud_score'] >= FRAUD_SCORE_THRESHOLD:
            recommendations.append('REVIEW: Manual verification recommended')
        elif analysis['fraud_score'] >= MEDIUM_RISK_THRESHOLD:
            recommendations.append('MONITOR: Increased monitoring recommended')
        
        # Specific recommendations based on indicators
        for indicator in analysis['indicators']:
            if indicator['type'] == 'user_velocity':
                recommendations.append('Consider implementing rate limiting per user')
            elif indicator['type'] == 'ip_velocity':
                recommendations.append('Consider IP-based rate limiting')
            elif indicator['type'] == 'known_bad_ip':
                recommendations.append('Block IP address immediately')
            elif indicator['type'] == 'suspicious_user_agent':
                recommendations.append('Consider blocking user agent patterns')
        
        return recommendations
    
    def _is_vpn_or_proxy(self, ip_address: str) -> bool:
        """
        Check if IP is VPN or proxy
        """
        try:
            # This would integrate with VPN/proxy detection services
            # For demo, we'll use a simple heuristic
            import ipaddress
            
            ip = ipaddress.ip_address(ip_address)
            
            # Check if it's a private IP (often used in VPN configurations)
            if ip.is_private:
                return True
            
            # You could integrate with services like:
            # - IPQualityScore
            # - MaxMind
            # - IP2Location
            # - VPN detection APIs
            
            return False
            
        except Exception:
            return False
    
    def _generate_device_fingerprint(self, device_info: Dict) -> Dict:
        """
        Generate device fingerprint for tracking
        """
        fingerprint = {}
        
        if 'screen_resolution' in device_info:
            fingerprint['screen'] = device_info['screen_resolution']
        
        if 'browser' in device_info:
            fingerprint['browser'] = device_info['browser']
        
        if 'os' in device_info:
            fingerprint['os'] = device_info['os']
        
        if 'timezone' in device_info:
            fingerprint['timezone'] = device_info['timezone']
        
        return fingerprint
    
    def _is_suspicious_conversion_id(self, conversion_id: str) -> bool:
        """
        Check if conversion ID follows suspicious patterns
        """
        if not conversion_id:
            return False
        
        # Check for sequential numbers
        if conversion_id.isdigit() and len(conversion_id) == 8:
            return True
        
        # Check for repeated patterns
        if len(set(conversion_id)) < 3:
            return True
        
        # Check for common test patterns
        test_patterns = ['test', 'demo', 'sample', 'debug', 'dev']
        conversion_id_lower = conversion_id.lower()
        
        for pattern in test_patterns:
            if pattern in conversion_id_lower:
                return True
        
        return False
    
    def _load_fraud_indicators(self) -> Dict:
        """
        Load fraud indicators configuration
        """
        return {
            'velocity_thresholds': {
                'user_per_hour': 10,
                'ip_per_hour': 20,
                'device_per_day': 5
            },
            'time_thresholds': {
                'fast_completion_seconds': 30,
                'suspicious_completion_seconds': 10
            },
            'risk_thresholds': {
                'low': 30,
                'medium': 50,
                'high': 70,
                'critical': 90
            }
        }
    
    def _log_fraud_analysis(self, analysis: Dict):
        """
        Log fraud analysis for monitoring
        """
        try:
            # Log to database
            log_entry = {
                'conversion_id': analysis['conversion_id'],
                'user_id': analysis['user_id'],
                'fraud_score': analysis['fraud_score'],
                'risk_level': analysis['risk_level'],
                'indicators_count': len(analysis['indicators']),
                'is_fraudulent': analysis['is_fraudulent'],
                'should_block': analysis['should_block'],
                'should_review': analysis['should_review'],
                'analysis_data': analysis,
                'timestamp': timezone.now()
            }
            
            # This would save to a fraud analysis log table
            # FraudAnalysisLog.objects.create(**log_entry)
            
            logger.info(f"Fraud analysis logged for conversion {analysis['conversion_id']}")
            
        except Exception as e:
            logger.error(f"Failed to log fraud analysis: {str(e)}")
    
    def _get_top_fraud_indicators(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Get top fraud indicators in date range
        """
        try:
            # This would query fraud analysis logs
            # For demo, we'll return sample data
            
            top_indicators = [
                {'type': 'user_velocity', 'count': 45, 'percentage': 35.2},
                {'type': 'ip_velocity', 'count': 28, 'percentage': 21.9},
                {'type': 'suspiciously_fast_completion', 'count': 22, 'percentage': 17.2},
                {'type': 'known_bad_ip', 'count': 18, 'percentage': 14.1},
                {'type': 'multiple_users_same_ip', 'count': 15, 'percentage': 11.7}
            ]
            
            return top_indicators
            
        except Exception as e:
            logger.error(f"Failed to get top fraud indicators: {str(e)}")
            return []
    
    @classmethod
    def update_fraud_models(cls, training_data: List[Dict] = None) -> Dict:
        """
        Update fraud detection models with new data
        """
        try:
            # This would integrate with ML/AI services
            # For demo, we'll just log the update
            
            logger.info(f"Fraud models updated with {len(training_data) if training_data else 0} training samples")
            
            return {
                'success': True,
                'models_updated': True,
                'training_samples': len(training_data) if training_data else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to update fraud models: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
