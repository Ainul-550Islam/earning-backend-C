import logging
from typing import Dict, List, Any, Optional
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta
from ..models import (
    UserRiskProfile, FraudAttempt, FraudRule,
    DeviceFingerprint, IPReputation
)
from ..detectors import (
    MultiAccountDetector, VPNProxyDetector,
    ClickFraudDetector, DeviceFingerprinter,
    PatternAnalyzer
)

logger = logging.getLogger(__name__)

class FraudScoreCalculator:
    """
    Comprehensive fraud score calculation service
    Calculates risk scores based on multiple factors and detectors
    """
    
    def __init__(self, user):
        self.user = user
        self.now = timezone.now()
        
        # Initialize detectors
        self.detectors = {
            'multi_account': MultiAccountDetector(),
            'vpn_proxy': VPNProxyDetector(),
            'click_fraud': ClickFraudDetector(),
            'device_fingerprint': DeviceFingerprinter(),
            'pattern_analyzer': PatternAnalyzer()
        }
        
        # Score weights
        self.weights = {
            'account_risk': 30,
            'behavior_risk': 25,
            'payment_risk': 20,
            'device_risk': 15,
            'network_risk': 10
        }
    
    def calculate_overall_risk(self) -> int:
        """
        Calculate overall risk score for user
        """
        try:
            risk_factors = self._collect_risk_factors()
            weighted_score = self._calculate_weighted_score(risk_factors)
            
            # Apply adjustments
            adjusted_score = self._apply_adjustments(weighted_score, risk_factors)
            
            # Cap at 100
            final_score = min(100, adjusted_score)
            
            # Update user risk profile
            self._update_risk_profile(final_score, risk_factors)
            
            return final_score
            
        except Exception as e:
            logger.error(f"Error calculating risk score: {e}")
            return 0
    
    def calculate_risk_breakdown(self) -> Dict:
        """
        Calculate detailed risk breakdown
        """
        risk_factors = self._collect_risk_factors()
        
        return {
            'overall_score': self.calculate_overall_risk(),
            'breakdown': risk_factors,
            'weights': self.weights,
            'calculated_at': self.now.isoformat(),
            'user_id': self.user.id
        }
    
    def _collect_risk_factors(self) -> Dict:
        """
        Collect all risk factors for the user
        """
        risk_factors = {
            'account_risk': self._calculate_account_risk(),
            'behavior_risk': self._calculate_behavior_risk(),
            'payment_risk': self._calculate_payment_risk(),
            'device_risk': self._calculate_device_risk(),
            'network_risk': self._calculate_network_risk(),
            'historical_risk': self._calculate_historical_risk(),
            'social_risk': self._calculate_social_risk()
        }
        
        return risk_factors
    
    def _calculate_account_risk(self) -> Dict:
        """
        Calculate account-related risk factors
        """
        risk_score = 0
        factors = []
        
        # 1. Account age
        account_age_days = (self.now - self.user.date_joined).days
        if account_age_days < 1:
            risk_score += 40
            factors.append('New account (< 1 day)')
        elif account_age_days < 7:
            risk_score += 20
            factors.append('Recent account (< 7 days)')
        
        # 2. Email verification
        if not self.user.is_verified:
            risk_score += 15
            factors.append('Email not verified')
        
        # 3. Profile completeness
        profile_fields = ['first_name', 'last_name', 'phone_number']
        missing_fields = sum(1 for field in profile_fields if not getattr(self.user, field, None))
        
        if missing_fields >= 2:
            risk_score += 10
            factors.append(f'Missing {missing_fields} profile fields')
        
        # 4. KYC status
        try:
            from kyc.models import KYCVerification
            kyc_status = KYCVerification.objects.filter(user=self.user).order_by('-created_at').first()
            
            if not kyc_status or kyc_status.status != 'verified':
                risk_score += 25
                factors.append('KYC not verified')
        except ImportError:
            pass
        
        return {
            'score': min(100, risk_score),
            'factors': factors,
            'account_age_days': account_age_days,
            'is_verified': self.user.is_verified
        }
    
    def _calculate_behavior_risk(self) -> Dict:
        """
        Calculate behavioral risk factors
        """
        try:
            from engagement.models import UserActivity, EngagementMetric
            
            risk_score = 0
            factors = []
            
            # 1. Activity frequency
            thirty_days_ago = self.now - timedelta(days=30)
            
            total_activities = UserActivity.objects.filter(
                user=self.user,
                timestamp__gte=thirty_days_ago
            ).count()
            
            if total_activities == 0:
                risk_score += 30
                factors.append('No activity in last 30 days')
            elif total_activities > 1000:
                risk_score += 25
                factors.append(f'Excessive activity: {total_activities} actions')
            
            # 2. Engagement metrics
            engagement_metrics = EngagementMetric.objects.filter(
                user=self.user,
                timestamp__gte=thirty_days_ago
            ).aggregate(
                avg_session=Avg('session_duration'),
                avg_actions=Avg('action_count')
            )
            
            avg_session = engagement_metrics.get('avg_session') or 0
            avg_actions = engagement_metrics.get('avg_actions') or 0
            
            if avg_session > 0 and avg_session < 10:  # Sessions too short
                risk_score += 15
                factors.append(f'Very short sessions: {avg_session:.1f}s average')
            
            if avg_actions > 50:  # Too many actions per session
                risk_score += 20
                factors.append(f'High actions per session: {avg_actions:.1f}')
            
            # 3. Pattern analysis
            pattern_data = {
                'user_id': self.user.id,
                'timeframe': '30d'
            }
            
            pattern_result = self.detectors['pattern_analyzer'].detect(pattern_data)
            pattern_score = pattern_result.get('fraud_score', 0)
            
            if pattern_score >= 40:
                risk_score += pattern_score * 0.5
                factors.append(f'Pattern analysis risk: {pattern_score}')
            
            return {
                'score': min(100, risk_score),
                'factors': factors,
                'total_activities': total_activities,
                'avg_session_duration': avg_session,
                'avg_actions_per_session': avg_actions,
                'pattern_score': pattern_score
            }
            
        except Exception as e:
            logger.error(f"Error calculating behavior risk: {e}")
            return {'score': 0, 'factors': [], 'error': str(e)}
    
    def _calculate_payment_risk(self) -> Dict:
        """
        Calculate payment-related risk factors
        """
        try:
            from wallet.models import WalletTransaction
            
            risk_score = 0
            factors = []
            
            thirty_days_ago = self.now - timedelta(days=30)
            
            # 1. Transaction patterns
            transactions = WalletTransaction.objects.filter(
                user=self.user,
                created_at__gte=thirty_days_ago
            )
            
            total_transactions = transactions.count()
            
            if total_transactions == 0:
                return {
                    'score': 10,  # Low risk but suspicious
                    'factors': ['No transactions in last 30 days'],
                    'total_transactions': 0
                }
            
            # 2. Credit vs Debit ratio
            credit_tx = transactions.filter(transaction_type='credit').count()
            debit_tx = transactions.filter(transaction_type='debit').count()
            
            if total_transactions > 0:
                credit_ratio = credit_tx / total_transactions
                
                if credit_ratio > 0.9:
                    risk_score += 25
                    factors.append(f'High credit ratio: {credit_ratio:.1%}')
            
            # 3. Amount patterns
            amounts = [float(tx.amount) for tx in transactions]
            
            if amounts:
                avg_amount = sum(amounts) / len(amounts)
                max_amount = max(amounts)
                
                if max_amount > avg_amount * 10:
                    risk_score += 20
                    factors.append(f'Large transaction outliers: {max_amount:.2f} vs avg {avg_amount:.2f}')
            
            # 4. Failed transactions
            failed_tx = transactions.filter(status='failed').count()
            
            if failed_tx > 0:
                failure_rate = failed_tx / total_transactions
                if failure_rate > 0.3:
                    risk_score += 30
                    factors.append(f'High failure rate: {failure_rate:.1%}')
            
            # 5. Withdrawal patterns
            withdrawals = transactions.filter(
                transaction_type='debit',
                status='completed'
            )
            
            withdrawal_count = withdrawals.count()
            total_withdrawn = sum(float(tx.amount) for tx in withdrawals)
            
            if withdrawal_count > 10:
                risk_score += 15
                factors.append(f'High withdrawal count: {withdrawal_count}')
            
            return {
                'score': min(100, risk_score),
                'factors': factors,
                'total_transactions': total_transactions,
                'credit_debit_ratio': f'{credit_tx}:{debit_tx}',
                'withdrawal_count': withdrawal_count,
                'total_withdrawn': total_withdrawn
            }
            
        except Exception as e:
            logger.error(f"Error calculating payment risk: {e}")
            return {'score': 0, 'factors': [], 'error': str(e)}
    
    def _calculate_device_risk(self) -> Dict:
        """
        Calculate device-related risk factors
        """
        try:
            risk_score = 0
            factors = []
            
            # 1. Device count
            devices = DeviceFingerprint.objects.filter(user=self.user)
            device_count = devices.count()
            
            if device_count > 3:
                risk_score += 25
                factors.append(f'Multiple devices: {device_count}')
            
            # 2. Device trust scores
            low_trust_devices = devices.filter(trust_score__lt=50).count()
            
            if low_trust_devices > 0:
                risk_score += 30
                factors.append(f'{low_trust_devices} devices with low trust score')
            
            # 3. Device fingerprint analysis
            if device_count > 0:
                latest_device = devices.order_by('-last_seen').first()
                
                device_data = {
                    'user_agent': latest_device.user_agent,
                    'device_data': {
                        'screen_width': latest_device.screen_resolution,
                        'timezone': latest_device.timezone,
                        'is_vpn': latest_device.is_vpn,
                        'is_proxy': latest_device.is_proxy
                    },
                    'user_id': self.user.id
                }
                
                device_result = self.detectors['device_fingerprint'].detect(device_data)
                device_score = device_result.get('fraud_score', 0)
                
                if device_score >= 40:
                    risk_score += device_score * 0.6
                    factors.append(f'Device fingerprint risk: {device_score}')
            
            return {
                'score': min(100, risk_score),
                'factors': factors,
                'device_count': device_count,
                'low_trust_devices': low_trust_devices,
                'latest_device_trust': latest_device.trust_score if device_count > 0 else None
            }
            
        except Exception as e:
            logger.error(f"Error calculating device risk: {e}")
            return {'score': 0, 'factors': [], 'error': str(e)}
    
    def _calculate_network_risk(self) -> Dict:
        """
        Calculate network-related risk factors
        """
        try:
            from engagement.models import UserActivity
            
            risk_score = 0
            factors = []
            
            thirty_days_ago = self.now - timedelta(days=30)
            
            # 1. IP diversity
            unique_ips = UserActivity.objects.filter(
                user=self.user,
                timestamp__gte=thirty_days_ago
            ).exclude(
                ip_address__isnull=True
            ).values_list('ip_address', flat=True).distinct().count()
            
            if unique_ips > 5:
                risk_score += 20
                factors.append(f'High IP diversity: {unique_ips} unique IPs')
            
            # 2. IP reputation
            suspicious_ips = []
            for activity in UserActivity.objects.filter(
                user=self.user,
                timestamp__gte=thirty_days_ago,
                ip_address__isnull=False
            ).distinct('ip_address'):
                
                ip_reputation = IPReputation.objects.filter(
                    ip_address=activity.ip_address
                ).first()
                
                if ip_reputation and ip_reputation.fraud_score >= 60:
                    suspicious_ips.append({
                        'ip': activity.ip_address,
                        'fraud_score': ip_reputation.fraud_score
                    })
            
            if suspicious_ips:
                risk_score += 35
                factors.append(f'{len(suspicious_ips)} suspicious IPs detected')
            
            # 3. VPN/Proxy detection
            vpn_ips = UserActivity.objects.filter(
                user=self.user,
                timestamp__gte=thirty_days_ago,
                ip_address__isnull=False
            ).exclude(
                ip_address__isnull=True
            ).distinct('ip_address')
            
            vpn_count = 0
            for activity in vpn_ips:
                vpn_data = {
                    'ip_address': activity.ip_address,
                    'user_id': self.user.id
                }
                
                vpn_result = self.detectors['vpn_proxy'].detect(vpn_data)
                if vpn_result.get('fraud_score', 0) >= 50:
                    vpn_count += 1
            
            if vpn_count > 0:
                risk_score += 40
                factors.append(f'{vpn_count} VPN/Proxy IPs detected')
            
            return {
                'score': min(100, risk_score),
                'factors': factors,
                'unique_ips': unique_ips,
                'suspicious_ips': suspicious_ips,
                'vpn_proxy_count': vpn_count
            }
            
        except Exception as e:
            logger.error(f"Error calculating network risk: {e}")
            return {'score': 0, 'factors': [], 'error': str(e)}
    
    def _calculate_historical_risk(self) -> Dict:
        """
        Calculate historical fraud risk
        """
        risk_score = 0
        factors = []
        
        # 1. Previous fraud attempts
        fraud_attempts = FraudAttempt.objects.filter(user=self.user)
        total_attempts = fraud_attempts.count()
        confirmed_attempts = fraud_attempts.filter(status='confirmed').count()
        
        if total_attempts > 0:
            risk_score += min(50, total_attempts * 10)
            factors.append(f'{total_attempts} fraud attempts')
            
            if confirmed_attempts > 0:
                risk_score += 40
                factors.append(f'{confirmed_attempts} confirmed fraud attempts')
        
        # 2. Risk profile history
        risk_profile = UserRiskProfile.objects.filter(user=self.user).first()
        
        if risk_profile:
            if risk_profile.overall_risk_score >= 70:
                risk_score += 30
                factors.append(f'High historical risk score: {risk_profile.overall_risk_score}')
            
            if risk_profile.is_flagged:
                risk_score += 50
                factors.append('Account is flagged')
            
            if risk_profile.is_restricted:
                risk_score += 60
                factors.append('Account is restricted')
        
        return {
            'score': min(100, risk_score),
            'factors': factors,
            'total_fraud_attempts': total_attempts,
            'confirmed_fraud_attempts': confirmed_attempts,
            'previously_flagged': risk_profile.is_flagged if risk_profile else False
        }
    
    def _calculate_social_risk(self) -> Dict:
        """
        Calculate social/referral risk factors
        """
        try:
            from referral.models import Referral
            
            risk_score = 0
            factors = []
            
            thirty_days_ago = self.now - timedelta(days=30)
            
            # 1. Referral patterns
            referrals = Referral.objects.filter(
                referrer=self.user,
                created_at__gte=thirty_days_ago
            )
            
            referral_count = referrals.count()
            
            if referral_count > 20:
                risk_score += 25
                factors.append(f'High referral count: {referral_count}')
            
            # 2. Referral conversion rate
            if referral_count > 0:
                successful_referrals = referrals.filter(status='completed').count()
                conversion_rate = (successful_referrals / referral_count) * 100
                
                if conversion_rate > 90:
                    risk_score += 35
                    factors.append(f'Unrealistic conversion rate: {conversion_rate:.1f}%')
                elif conversion_rate > 70:
                    risk_score += 20
                    factors.append(f'High conversion rate: {conversion_rate:.1f}%')
            
            # 3. Social graph analysis
            # Check if user is part of suspicious referral chains
            
            return {
                'score': min(100, risk_score),
                'factors': factors,
                'referral_count': referral_count,
                'conversion_rate': conversion_rate if referral_count > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error calculating social risk: {e}")
            return {'score': 0, 'factors': [], 'error': str(e)}
    
    def _calculate_weighted_score(self, risk_factors: Dict) -> float:
        """
        Calculate weighted risk score
        """
        weighted_sum = 0
        total_weight = 0
        
        for factor_type, factor_data in risk_factors.items():
            weight_key = factor_type.replace('_risk', '')
            weight = self.weights.get(weight_key, 10)
            
            factor_score = factor_data.get('score', 0)
            weighted_sum += factor_score * (weight / 100)
            total_weight += weight / 100
        
        if total_weight > 0:
            return weighted_sum / total_weight
        
        return 0
    
    def _apply_adjustments(self, base_score: float, risk_factors: Dict) -> float:
        """
        Apply adjustments to base score
        """
        adjusted_score = base_score
        
        # 1. Age adjustment (older accounts are lower risk)
        account_age_days = risk_factors.get('account_risk', {}).get('account_age_days', 0)
        if account_age_days > 365:
            adjusted_score *= 0.7  # 30% reduction for accounts > 1 year
        elif account_age_days > 90:
            adjusted_score *= 0.8  # 20% reduction for accounts > 3 months
        
        # 2. High-risk factor multiplier
        high_risk_factors = sum(1 for factor in risk_factors.values() 
                               if factor.get('score', 0) >= 60)
        
        if high_risk_factors >= 2:
            adjusted_score *= 1.3  # 30% increase for multiple high-risk factors
        
        # 3. Payment history adjustment
        payment_risk = risk_factors.get('payment_risk', {})
        if payment_risk.get('total_transactions', 0) > 10 and payment_risk.get('score', 0) < 20:
            adjusted_score *= 0.9  # 10% reduction for good payment history
        
        return adjusted_score
    
    def _update_risk_profile(self, final_score: int, risk_factors: Dict):
        """
        Update user's risk profile
        """
        try:
            risk_profile, created = UserRiskProfile.objects.get_or_create(user=self.user)
            
            # Update scores
            risk_profile.overall_risk_score = final_score
            risk_profile.account_risk_score = risk_factors.get('account_risk', {}).get('score', 0)
            risk_profile.payment_risk_score = risk_factors.get('payment_risk', {}).get('score', 0)
            risk_profile.behavior_risk_score = risk_factors.get('behavior_risk', {}).get('score', 0)
            
            # Update risk factors
            all_factors = []
            for factor_data in risk_factors.values():
                all_factors.extend(factor_data.get('factors', []))
            
            risk_profile.risk_factors = {
                'factors': all_factors[:10],  # Keep only top 10
                'calculated_at': self.now.isoformat()
            }
            
            # Update warning flags
            warning_flags = []
            if final_score >= 80:
                warning_flags.append('high_risk')
            if final_score >= 60:
                warning_flags.append('medium_risk')
            
            risk_factors_scores = [data.get('score', 0) for data in risk_factors.values()]
            if any(score >= 70 for score in risk_factors_scores):
                warning_flags.append('high_risk_factor')
            
            risk_profile.warning_flags = warning_flags
            
            # Update statistics
            fraud_attempts = FraudAttempt.objects.filter(user=self.user)
            risk_profile.total_fraud_attempts = fraud_attempts.count()
            risk_profile.confirmed_fraud_attempts = fraud_attempts.filter(status='confirmed').count()
            
            # Set monitoring level
            if final_score >= 80:
                risk_profile.monitoring_level = 'strict'
                risk_profile.is_flagged = True
            elif final_score >= 60:
                risk_profile.monitoring_level = 'enhanced'
                risk_profile.is_flagged = True
            else:
                risk_profile.monitoring_level = 'normal'
                risk_profile.is_flagged = False
            
            # Set next assessment
            if final_score >= 80:
                next_assessment = self.now + timedelta(hours=1)
            elif final_score >= 60:
                next_assessment = self.now + timedelta(hours=6)
            else:
                next_assessment = self.now + timedelta(days=1)
            
            risk_profile.last_risk_assessment = self.now
            risk_profile.next_assessment_due = next_assessment
            
            risk_profile.save()
            
            logger.info(f"Updated risk profile for user {self.user.id}: score={final_score}")
            
        except Exception as e:
            logger.error(f"Error updating risk profile: {e}")
    
    def get_risk_recommendations(self) -> List[Dict]:
        """
        Get risk mitigation recommendations
        """
        risk_factors = self._collect_risk_factors()
        recommendations = []
        
        # Account risk recommendations
        account_risk = risk_factors.get('account_risk', {})
        if account_risk.get('score', 0) >= 30:
            recommendations.append({
                'type': 'account',
                'priority': 'high',
                'action': 'Complete KYC verification',
                'reason': 'Account verification reduces fraud risk'
            })
        
        # Payment risk recommendations
        payment_risk = risk_factors.get('payment_risk', {})
        if payment_risk.get('score', 0) >= 40:
            recommendations.append({
                'type': 'payment',
                'priority': 'high',
                'action': 'Review transaction patterns',
                'reason': 'Unusual payment patterns detected'
            })
        
        # Device risk recommendations
        device_risk = risk_factors.get('device_risk', {})
        if device_risk.get('score', 0) >= 50:
            recommendations.append({
                'type': 'device',
                'priority': 'medium',
                'action': 'Check device security',
                'reason': 'Suspicious device activity detected'
            })
        
        # Network risk recommendations
        network_risk = risk_factors.get('network_risk', {})
        if network_risk.get('score', 0) >= 60:
            recommendations.append({
                'type': 'network',
                'priority': 'high',
                'action': 'Investigate IP addresses',
                'reason': 'Suspicious network activity detected'
            })
        
        return recommendations
    
    def calculate_action_required(self, threshold: int = 70) -> Dict:
        """
        Determine if action is required based on risk score
        """
        overall_score = self.calculate_overall_risk()
        
        action_required = overall_score >= threshold
        
        actions = []
        if overall_score >= 90:
            actions = ['immediate_review', 'potential_suspension', 'enhanced_monitoring']
        elif overall_score >= 80:
            actions = ['review_required', 'temporary_restrictions', 'additional_verification']
        elif overall_score >= 70:
            actions = ['monitor_closely', 'flag_for_review']
        elif overall_score >= 60:
            actions = ['watch_list', 'periodic_review']
        
        return {
            'action_required': action_required,
            'score': overall_score,
            'threshold': threshold,
            'recommended_actions': actions,
            'risk_level': self._get_risk_level(overall_score)
        }
    
    def _get_risk_level(self, score: int) -> str:
        """Get risk level description"""
        if score >= 90:
            return 'critical'
        elif score >= 80:
            return 'high'
        elif score >= 70:
            return 'elevated'
        elif score >= 60:
            return 'medium'
        elif score >= 40:
            return 'low'
        else:
            return 'minimal'