"""
Advanced Risk Scoring Engine
Machine Learning-based risk assessment for user activities
"""
import logging
import numpy as np
from typing import Dict, List, Tuple
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)


class RiskScoringEngine:
    """
    Advanced risk scoring using multiple factors and ML algorithms
    
    Risk factors analyzed:
    - Historical behavior patterns
    - Transaction patterns
    - Device trust score
    - IP reputation
    - Account age and activity
    - Social connections
    - Earning patterns
    - Withdrawal patterns
    """
    
    # Feature weights for risk calculation
    WEIGHTS = {
        'device_trust': 0.20,
        'ip_reputation': 0.18,
        'behavioral_score': 0.15,
        'transaction_pattern': 0.12,
        'account_history': 0.10,
        'earning_pattern': 0.10,
        'social_signals': 0.08,
        'time_based_factors': 0.07,
    }
    
    def __init__(self, user):
        """
        Initialize risk scoring engine
        
        Args:
            user: User instance to score
        """
        self.user = user
        self.risk_factors = {}
        self.risk_score = 0
    
    def calculate_comprehensive_risk_score(self) -> Dict:
        """
        Calculate comprehensive risk score for user
        
        Returns:
            Risk assessment dictionary
        """
        try:
            # Calculate individual risk factors
            device_score = self._calculate_device_risk()
            ip_score = self._calculate_ip_risk()
            behavioral_score = self._calculate_behavioral_risk()
            transaction_score = self._calculate_transaction_risk()
            account_score = self._calculate_account_history_risk()
            earning_score = self._calculate_earning_pattern_risk()
            social_score = self._calculate_social_risk()
            time_score = self._calculate_time_based_risk()
            
            # Store individual scores
            self.risk_factors = {
                'device_trust': device_score,
                'ip_reputation': ip_score,
                'behavioral_score': behavioral_score,
                'transaction_pattern': transaction_score,
                'account_history': account_score,
                'earning_pattern': earning_score,
                'social_signals': social_score,
                'time_based_factors': time_score,
            }
            
            # Calculate weighted risk score
            total_risk = 0
            for factor, score in self.risk_factors.items():
                weight = self.WEIGHTS.get(factor, 0)
                total_risk += score * weight
            
            self.risk_score = min(int(total_risk), 100)
            
            # Determine risk level
            risk_level = self._determine_risk_level(self.risk_score)
            
            # Generate recommendations
            recommendations = self._generate_recommendations()
            
            result = {
                'user_id': str(self.user.id),
                'risk_score': self.risk_score,
                'risk_level': risk_level,
                'risk_factors': self.risk_factors,
                'recommendations': recommendations,
                'calculated_at': timezone.now(),
            }
            
            # Save to database
            self._save_risk_profile(result)
            
            logger.info(f"Risk score calculated for user {self.user.id}: {self.risk_score}")
            
            return result
        
        except Exception as e:
            logger.error(f"Error calculating risk score: {e}")
            return {
                'risk_score': 50,
                'risk_level': 'medium',
                'error': str(e)
            }
    
    def _calculate_device_risk(self) -> int:
        """Calculate device-based risk score (0-100)"""
        try:
            from api.fraud_detection.models import DeviceFingerprint
            
            devices = DeviceFingerprint.objects.filter(user=self.user)
            
            if not devices.exists():
                return 30  # New user, moderate risk
            
            risk = 0
            
            # Check number of devices
            device_count = devices.count()
            if device_count > 5:
                risk += 20
            elif device_count > 3:
                risk += 10
            
            # Check device trust scores
            avg_trust = devices.aggregate(avg=models.Avg('trust_score'))['avg'] or 100
            risk += (100 - avg_trust) * 0.3
            
            # Check for VPN/Proxy usage
            vpn_count = devices.filter(is_vpn=True).count()
            if vpn_count > 0:
                risk += vpn_count * 15
            
            proxy_count = devices.filter(is_proxy=True).count()
            if proxy_count > 0:
                risk += proxy_count * 15
            
            # Check for bot flags
            if devices.filter(is_bot=True).exists():
                risk += 40
            
            # Check device sharing (multiple users on same device)
            for device in devices:
                shared_users = DeviceFingerprint.objects.filter(
                    device_hash=device.device_hash
                ).values('user').distinct().count()
                
                if shared_users > 1:
                    risk += min(shared_users * 10, 30)
            
            return min(int(risk), 100)
        
        except Exception as e:
            logger.error(f"Device risk calculation error: {e}")
            return 50
    
    def _calculate_ip_risk(self) -> int:
        """Calculate IP reputation risk score"""
        try:
            from api.fraud_detection.models import DeviceFingerprint, IPReputation
            
            # Get user's recent IPs
            recent_devices = DeviceFingerprint.objects.filter(
                user=self.user,
                last_seen__gte=timezone.now() - timedelta(days=30)
            )
            
            if not recent_devices.exists():
                return 20
            
            risk = 0
            ip_addresses = recent_devices.values_list('ip_address', flat=True).distinct()
            
            for ip in ip_addresses:
                try:
                    ip_rep = IPReputation.objects.get(ip_address=ip)
                    
                    # Add fraud score
                    risk += ip_rep.fraud_score * 0.5
                    
                    # Check blacklist
                    if ip_rep.is_blacklisted:
                        risk += 40
                    
                    # Check threat types
                    if 'vpn' in ip_rep.threat_types:
                        risk += 15
                    if 'proxy' in ip_rep.threat_types:
                        risk += 15
                    if 'tor' in ip_rep.threat_types:
                        risk += 25
                
                except IPReputation.DoesNotExist:
                    # Unknown IP, moderate risk
                    risk += 10
            
            # Check IP hopping (too many different IPs)
            if len(ip_addresses) > 10:
                risk += 20
            elif len(ip_addresses) > 5:
                risk += 10
            
            return min(int(risk / len(ip_addresses)), 100) if ip_addresses else 20
        
        except Exception as e:
            logger.error(f"IP risk calculation error: {e}")
            return 30
    
    def _calculate_behavioral_risk(self) -> int:
        """Calculate behavioral pattern risk"""
        try:
            from api.fraud_detection.models import FraudAttempt
            from api.engagement.models import UserActivity
            
            risk = 0
            
            # Check fraud attempts history
            fraud_attempts = FraudAttempt.objects.filter(
                user=self.user,
                created_at__gte=timezone.now() - timedelta(days=90)
            )
            
            fraud_count = fraud_attempts.count()
            confirmed_fraud = fraud_attempts.filter(status='confirmed').count()
            
            risk += min(fraud_count * 10, 50)
            risk += min(confirmed_fraud * 20, 60)
            
            # Check activity patterns
            activities = UserActivity.objects.filter(
                user=self.user,
                timestamp__gte=timezone.now() - timedelta(days=30)
            )
            
            if activities.exists():
                # Check for bot-like behavior (too regular patterns)
                activity_times = list(activities.values_list('timestamp__hour', flat=True))
                
                if activity_times:
                    # Calculate variance
                    variance = np.var(activity_times) if len(activity_times) > 1 else 0
                    
                    # Very low variance = bot-like behavior
                    if variance < 1:
                        risk += 30
                    elif variance < 3:
                        risk += 15
                
                # Check activity frequency
                daily_activities = activities.values('timestamp__date').annotate(
                    count=models.Count('id')
                )
                
                avg_daily = sum(d['count'] for d in daily_activities) / len(daily_activities) if daily_activities else 0
                
                # Too many activities = suspicious
                if avg_daily > 100:
                    risk += 25
                elif avg_daily > 50:
                    risk += 15
            
            return min(int(risk), 100)
        
        except Exception as e:
            logger.error(f"Behavioral risk calculation error: {e}")
            return 20
    
    def _calculate_transaction_risk(self) -> int:
        """Calculate transaction pattern risk"""
        try:
            from api.wallet.models import Transaction
            
            risk = 0
            
            # Get recent transactions
            transactions = Transaction.objects.filter(
                user=self.user,
                created_at__gte=timezone.now() - timedelta(days=30)
            )
            
            if not transactions.exists():
                return 10  # No transactions yet
            
            # Check suspicious patterns
            
            # 1. Too many failed transactions
            failed_txns = transactions.filter(status='failed').count()
            total_txns = transactions.count()
            
            if total_txns > 0:
                failure_rate = (failed_txns / total_txns) * 100
                
                if failure_rate > 50:
                    risk += 30
                elif failure_rate > 30:
                    risk += 15
            
            # 2. Check for round-trip transactions (deposit then immediate withdraw)
            credits = transactions.filter(transaction_type='credit')
            debits = transactions.filter(transaction_type='debit')
            
            for credit in credits[:10]:  # Check last 10 credits
                # Check if there's a withdrawal within 1 hour
                quick_withdrawal = debits.filter(
                    created_at__gte=credit.created_at,
                    created_at__lte=credit.created_at + timedelta(hours=1),
                    amount__gte=credit.amount * Decimal('0.8')  # 80% or more
                ).exists()
                
                if quick_withdrawal:
                    risk += 15
            
            # 3. Check transaction amounts
            total_credits = credits.aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0')
            
            # Suspiciously high earnings in short time
            if total_credits > Decimal('1000'):
                risk += 20
            elif total_credits > Decimal('500'):
                risk += 10
            
            return min(int(risk), 100)
        
        except Exception as e:
            logger.error(f"Transaction risk calculation error: {e}")
            return 15
    
    def _calculate_account_history_risk(self) -> int:
        """Calculate account age and history risk"""
        try:
            risk = 0
            
            # Account age
            account_age = (timezone.now() - self.user.created_at).days
            
            # Very new accounts are higher risk
            if account_age < 1:
                risk += 40
            elif account_age < 7:
                risk += 25
            elif account_age < 30:
                risk += 15
            elif account_age < 90:
                risk += 5
            
            # Check verification status
            if not self.user.is_verified:
                risk += 20
            
            # Check email verification
            if not self.user.email_verified:
                risk += 15
            
            # Check profile completion
            if hasattr(self.user, 'profile'):
                profile = self.user.profile
                
                # Incomplete profiles are riskier
                if not profile.phone_number:
                    risk += 10
                if not profile.date_of_birth:
                    risk += 5
            else:
                risk += 15  # No profile at all
            
            # Check login activity
            from api.users.models import LoginHistory
            
            logins = LoginHistory.objects.filter(
                user=self.user,
                created_at__gte=timezone.now() - timedelta(days=30)
            ).count()
            
            # Too few logins for account age
            if account_age > 30 and logins < 5:
                risk += 15
            
            return min(int(risk), 100)
        
        except Exception as e:
            logger.error(f"Account history risk calculation error: {e}")
            return 20
    
    def _calculate_earning_pattern_risk(self) -> int:
        """Calculate earning pattern risk"""
        try:
            from api.offerwall.models import OfferConversion
            from api.wallet.models import Transaction
            
            risk = 0
            
            # Get earnings
            earnings = Transaction.objects.filter(
                user=self.user,
                transaction_type='credit',
                created_at__gte=timezone.now() - timedelta(days=30)
            )
            
            if not earnings.exists():
                return 5  # No earnings yet, low risk
            
            # Check offer completions
            conversions = OfferConversion.objects.filter(
                user=self.user,
                created_at__gte=timezone.now() - timedelta(days=30)
            )
            
            # Too many rejections
            rejected = conversions.filter(status='rejected').count()
            total_conversions = conversions.count()
            
            if total_conversions > 0:
                rejection_rate = (rejected / total_conversions) * 100
                
                if rejection_rate > 50:
                    risk += 35
                elif rejection_rate > 30:
                    risk += 20
            
            # Check earning velocity (too much too fast)
            total_earned = earnings.aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0')
            
            account_age_days = (timezone.now() - self.user.created_at).days or 1
            daily_avg = float(total_earned) / account_age_days
            
            if daily_avg > 100:  # $100/day average
                risk += 30
            elif daily_avg > 50:
                risk += 15
            
            # Check for offer abuse patterns
            # Same offer completed multiple times
            offer_completion_counts = conversions.values('offer').annotate(
                count=models.Count('id')
            ).filter(count__gt=1)
            
            if offer_completion_counts.exists():
                risk += min(offer_completion_counts.count() * 10, 30)
            
            return min(int(risk), 100)
        
        except Exception as e:
            logger.error(f"Earning pattern risk calculation error: {e}")
            return 10
    
    def _calculate_social_risk(self) -> int:
        """Calculate social signals risk"""
        try:
            from api.referral.models import Referral
            
            risk = 0
            
            # Check referral patterns
            referrals = Referral.objects.filter(referrer=self.user)
            referral_count = referrals.count()
            
            # Too many referrals too fast
            account_age_days = (timezone.now() - self.user.created_at).days or 1
            
            if account_age_days < 7 and referral_count > 10:
                risk += 30
            elif account_age_days < 30 and referral_count > 50:
                risk += 25
            
            # Check if referred users are active
            if referral_count > 0:
                active_referrals = 0
                
                for referral in referrals:
                    if referral.referred.last_login:
                        days_since_login = (timezone.now() - referral.referred.last_login).days
                        if days_since_login < 30:
                            active_referrals += 1
                
                activation_rate = (active_referrals / referral_count) * 100 if referral_count > 0 else 0
                
                # Low activation rate = fake referrals
                if activation_rate < 20 and referral_count > 10:
                    risk += 35
                elif activation_rate < 40:
                    risk += 15
            
            return min(int(risk), 100)
        
        except Exception as e:
            logger.error(f"Social risk calculation error: {e}")
            return 5
    
    def _calculate_time_based_risk(self) -> int:
        """Calculate time-based behavior risk"""
        try:
            from api.engagement.models import UserActivity
            
            risk = 0
            
            # Get activity timestamps
            activities = UserActivity.objects.filter(
                user=self.user,
                timestamp__gte=timezone.now() - timedelta(days=30)
            )
            
            if not activities.exists():
                return 10
            
            # Check activity distribution across hours
            hours = list(activities.values_list('timestamp__hour', flat=True))
            
            if hours:
                unique_hours = len(set(hours))
                
                # Bot-like behavior: active 24/7
                if unique_hours > 20:
                    risk += 25
                
                # Check for suspicious regular patterns
                from collections import Counter
                hour_counts = Counter(hours)
                
                # Too consistent
                if hour_counts:
                    max_count = max(hour_counts.values())
                    min_count = min(hour_counts.values())
                    
                    if max_count > 0 and min_count > 0:
                        consistency = min_count / max_count
                        
                        if consistency > 0.8:  # Very consistent = bot
                            risk += 20
            
            # Check session patterns
            from api.users.models import LoginHistory
            
            logins = LoginHistory.objects.filter(
                user=self.user,
                created_at__gte=timezone.now() - timedelta(days=30)
            )
            
            if logins.count() > 100:  # Too many logins
                risk += 15
            
            return min(int(risk), 100)
        
        except Exception as e:
            logger.error(f"Time-based risk calculation error: {e}")
            return 5
    
    def _determine_risk_level(self, risk_score: int) -> str:
        """Determine risk level from score"""
        if risk_score >= 80:
            return 'critical'
        elif risk_score >= 60:
            return 'high'
        elif risk_score >= 40:
            return 'medium'
        elif risk_score >= 20:
            return 'low'
        else:
            return 'minimal'
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on risk factors"""
        recommendations = []
        
        # High device risk
        if self.risk_factors.get('device_trust', 0) > 60:
            recommendations.append('VERIFY_DEVICE_OWNERSHIP')
            recommendations.append('LIMIT_DEVICE_COUNT')
        
        # High IP risk
        if self.risk_factors.get('ip_reputation', 0) > 60:
            recommendations.append('BLOCK_VPN_PROXY')
            recommendations.append('VERIFY_LOCATION')
        
        # Behavioral issues
        if self.risk_factors.get('behavioral_score', 0) > 60:
            recommendations.append('ENHANCED_MONITORING')
            recommendations.append('MANUAL_REVIEW_ACTIVITIES')
        
        # Transaction issues
        if self.risk_factors.get('transaction_pattern', 0) > 60:
            recommendations.append('LIMIT_WITHDRAWAL_AMOUNT')
            recommendations.append('DELAY_LARGE_TRANSACTIONS')
        
        # New account
        if self.risk_factors.get('account_history', 0) > 60:
            recommendations.append('COMPLETE_KYC_VERIFICATION')
            recommendations.append('LIMIT_DAILY_EARNINGS')
        
        # Earning abuse
        if self.risk_factors.get('earning_pattern', 0) > 60:
            recommendations.append('MANUAL_REVIEW_EARNINGS')
            recommendations.append('LIMIT_OFFER_COMPLETIONS')
        
        # Overall high risk
        if self.risk_score >= 80:
            recommendations.append('SUSPEND_ACCOUNT_PENDING_REVIEW')
        elif self.risk_score >= 60:
            recommendations.append('RESTRICT_HIGH_VALUE_ACTIONS')
        
        return list(set(recommendations))  # Remove duplicates
    
    def _save_risk_profile(self, risk_assessment: Dict) -> None:
        """Save risk assessment to database"""
        try:
            from api.fraud_detection.models import UserRiskProfile
            
            profile, created = UserRiskProfile.objects.get_or_create(user=self.user)
            
            profile.overall_risk_score = risk_assessment['risk_score']
            profile.risk_factors = risk_assessment['risk_factors']
            profile.last_risk_assessment = timezone.now()
            
            # Update monitoring level
            risk_level = risk_assessment['risk_level']
            if risk_level in ['critical', 'high']:
                profile.monitoring_level = 'strict'
            elif risk_level == 'medium':
                profile.monitoring_level = 'enhanced'
            else:
                profile.monitoring_level = 'normal'
            
            # Flag if high risk
            profile.is_flagged = risk_assessment['risk_score'] >= 70
            
            profile.save()
            
            logger.info(f"Risk profile saved for user {self.user.id}")
        
        except Exception as e:
            logger.error(f"Error saving risk profile: {e}")
            
           # api/users/services/risk_scoring.py ফাইলের একদম নিচে যোগ করুন

# ১. ক্লাসটিকে এমনভাবে ডিফাইন করুন যাতে user না দিলেও এরর না দেয়
# আপনার বিদ্যমান RiskScoringEngine ক্লাসের __init__ মেথডটি খুঁজে নিচের মতো করুন:
# def __init__(self, user=None): 
#     self.user = user

# ২. ফাইলের শেষে এই লাইনটি যোগ করুন যাতে সব ভিউ ফাইল একে খুঁজে পায়
risk_scoring_engine = RiskScoringEngine(user=None)