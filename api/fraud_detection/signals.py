import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import (
    FraudAttempt, FraudAlert, UserRiskProfile,
    DeviceFingerprint, IPReputation, OfferCompletion  # [OK] এখানে যোগ করুন
)
from api.users.models import User
from api.wallet.models import WalletTransaction
# [ERROR] এই লাইন মুছে দিন:
# from api.offerwall.models import OfferCompletion

logger = logging.getLogger(__name__)

@receiver(post_save, sender=FraudAttempt)
def handle_new_fraud_attempt(sender, instance, created, **kwargs):
    """
    Handle new fraud attempt detection
    """
    if created:
        try:
            from .services.AutoBanService import AutoBanService
            from .services.FraudScoreCalculator import FraudScoreCalculator
            
            # Process auto-ban if score is high
            if instance.fraud_score >= 70:
                auto_ban_service = AutoBanService()
                auto_ban_service.process_fraud_attempt(instance)
            
            # Update user risk score
            calculator = FraudScoreCalculator(instance.user)
            calculator.calculate_overall_risk()
            
            # Create alert for admin
            FraudAlert.objects.create(
                alert_type='rule_triggered',
                priority='high' if instance.fraud_score >= 70 else 'medium',
                title=f"New Fraud Attempt: {instance.get_attempt_type_display()}",
                description=f"User {instance.user.username} - Score: {instance.fraud_score}",
                user=instance.user,
                fraud_attempt=instance,
                data={
                    'fraud_score': instance.fraud_score,
                    'attempt_type': instance.attempt_type,
                    'detected_by': instance.detected_by
                }
            )
            
            logger.info(f"New fraud attempt handled: {instance.attempt_id}")
            
        except Exception as e:
            logger.error(f"Error handling new fraud attempt: {e}")

@receiver(post_save, sender=User)
def create_user_risk_profile(sender, instance, created, **kwargs):
    """
    Create risk profile for new users
    """
    if created:
        try:
            UserRiskProfile.objects.get_or_create(user=instance)
            logger.info(f"Risk profile created for user: {instance.id}")
        except Exception as e:
            logger.error(f"Error creating risk profile: {e}")

@receiver(pre_save, sender=WalletTransaction)
def check_transaction_fraud(sender, instance, **kwargs):
    """
    Check transactions for potential fraud (connects to wallet operations).
    """
    if instance.pk is None:  # New transaction
        try:
            user = getattr(instance.wallet, 'user', None) if instance.wallet_id else None
            if not user:
                return
            from .detectors.PatternAnalyzer import PatternAnalyzer

            risk_profile = UserRiskProfile.objects.filter(user=user).first()
            if risk_profile and risk_profile.is_flagged:
                return

            analyzer = PatternAnalyzer()
            txn_type = getattr(instance, 'type', None)
            amount_val = float(instance.amount) if instance.amount else 0
            if txn_type in ('earning', 'reward', 'referral', 'bonus', 'admin_credit') and amount_val > 1000:
                # Large credit transaction
                transaction_data = {
                    'user_id': user.id,
                    'activity_type': 'large_credit_transaction',
                    'metadata': {
                        'amount': amount_val,
                        'transaction_type': txn_type
                    }
                }

                result = analyzer.detect(transaction_data)
                if result.get('fraud_score', 0) >= 60:
                    FraudAttempt.objects.create(
                        user=user,
                        attempt_type='payment_fraud',
                        description=f"Large suspicious credit transaction: ${instance.amount}",
                        detected_by='WalletTransactionMonitor',
                        fraud_score=result['fraud_score'],
                        confidence_score=result['confidence'],
                        evidence_data=result.get('evidence', {}),
                        amount_involved=instance.amount
                    )
            
        except Exception as e:
            logger.error(f"Error checking transaction fraud: {e}")

@receiver(post_save, sender=OfferCompletion)
def check_offer_completion_fraud(sender, instance, created, **kwargs):
    """
    Check offer completions for fraud
    """
    if created and instance.status == 'completed':
        try:
            from .detectors.ClickFraudDetector import ClickFraudDetector
            
            # Check for click fraud patterns
            detector = ClickFraudDetector()
            
            click_data = {
                'user_id': instance.user_id,
                'offer_id': instance.offer_id,
                'click_data': {
                    'revenue': float(instance.reward_amount) if instance.reward_amount else 0,  # [OK] payout থেকে reward_amount এ পরিবর্তন
                    'completion_time': instance.completed_at.isoformat() if instance.completed_at else None
                }
            }
            
            result = detector.detect(click_data)
            if result.get('fraud_score', 0) >= 65:
                # Create fraud attempt
                FraudAttempt.objects.create(
                    user=instance.user,
                    attempt_type='click_fraud',
                    description=f"Suspicious offer completion: {instance.offer_id}",
                    detected_by='ClickFraudDetector',
                    fraud_score=result['fraud_score'],
                    confidence_score=result['confidence'],
                    evidence_data=result.get('evidence', {}),
                    amount_involved=instance.reward_amount or 0  # [OK] payout থেকে reward_amount এ পরিবর্তন
                )
            
        except Exception as e:
            logger.error(f"Error checking offer completion fraud: {e}")

@receiver(post_save, sender='referral.Referral')  # [OK] String reference ব্যবহার করা হয়েছে
def check_referral_fraud(sender, instance, created, **kwargs):
    """
    Check referrals for fraud
    """
    if created:
        try:
            from .detectors.MultiAccountDetector import MultiAccountDetector
            
            # Check for multi-account referral fraud
            detector = MultiAccountDetector()
            
            referral_data = {
                'user_id': instance.referrer_id,
                'ip_address': getattr(instance, 'ip_address', None),  # [OK] Safe access
                'device_data': instance.metadata.get('device_data', {}) if hasattr(instance, 'metadata') and instance.metadata else {}
            }
            
            result = detector.detect(referral_data)
            if result.get('fraud_score', 0) >= 70:
                # Create fraud attempt
                FraudAttempt.objects.create(
                    user=instance.referrer,
                    attempt_type='referral_fraud',
                    description=f"Suspicious referral: {getattr(instance, 'referred_email', 'N/A')}",
                    detected_by='MultiAccountDetector',
                    fraud_score=result['fraud_score'],
                    confidence_score=result['confidence'],
                    evidence_data=result.get('evidence', {}),
                    amount_involved=0
                )
            
        except Exception as e:
            logger.error(f"Error checking referral fraud: {e}")

@receiver(post_save, sender=DeviceFingerprint)
def update_device_trust_score(sender, instance, created, **kwargs):
    """
    Update device trust score based on fraud attempts
    """
    if not created:
        try:
            # Check if user has recent fraud attempts
            recent_fraud = FraudAttempt.objects.filter(
                user=instance.user,
                created_at__gte=timezone.now() - timezone.timedelta(days=30)
            ).exists()
            
            if recent_fraud:
                # Lower trust score
                DeviceFingerprint.objects.filter(pk=instance.pk).update(trust_score=max(0, instance.trust_score - 20))
            
        except Exception as e:
            logger.error(f"Error updating device trust score: {e}")

@receiver(post_save, sender=IPReputation)
def handle_ip_blacklist(sender, instance, **kwargs):
    """
    Handle IP blacklisting
    """
    if instance.is_blacklisted:
        try:
            # Create alert for blacklisted IP
            FraudAlert.objects.create(
                alert_type='system_anomaly',
                priority='high',
                title=f"IP Blacklisted: {instance.ip_address}",
                description=f"IP {instance.ip_address} added to blacklist: {instance.blacklist_reason}",
                data={
                    'ip_address': instance.ip_address,
                    'fraud_score': instance.fraud_score,
                    'blacklist_reason': instance.blacklist_reason
                }
            )
            
            logger.warning(f"IP blacklisted: {instance.ip_address}")
            
        except Exception as e:
            logger.error(f"Error handling IP blacklist: {e}")