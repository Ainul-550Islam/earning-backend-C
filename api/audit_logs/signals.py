"""
Signals for automatic audit logging on model changes and user actions
"""

from django.db.models.signals import post_save, post_delete, pre_save, m2m_changed
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.core.signals import request_started, request_finished, got_request_exception
from django.db import transaction
from django.utils import timezone
import json
import uuid

from .models import AuditLog, AuditLogAction, AuditLogLevel
from .services.LogService import LogService

User = get_user_model()
log_service = LogService()


# ===================== USER SIGNALS =====================
@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Log successful user login"""
    
    log_service.create_log(
        user=user,
        action=AuditLogAction.LOGIN,
        level=AuditLogLevel.INFO,
        message=f"User {user.email} logged in successfully",
        user_ip=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        request_method=request.method,
        request_path=request.path,
        metadata={
            'login_method': 'password',  # or 'social', 'otp', etc.
            'session_id': request.session.session_key if hasattr(request, 'session') else None,
            'is_first_login': user.last_login is None,
            'login_source': request.META.get('HTTP_REFERER', 'direct')
        }
    )

    # Run quick fraud risk assessment on login (best-effort, non-blocking)
    try:
        from api.fraud_detection.services.FraudScoreCalculator import FraudScoreCalculator
        from api.fraud_detection.services.AutoBanService import AutoBanService
        from api.fraud_detection.models import FraudAttempt

        # Build minimal detection data
        ip = request.META.get('REMOTE_ADDR') or request.META.get('HTTP_X_FORWARDED_FOR')
        ua = request.META.get('HTTP_USER_AGENT', '')

        calculator = FraudScoreCalculator(user)
        # Provide basic device/network context where possible
        # This will internally call detectors and update UserRiskProfile
        risk_info = calculator.calculate_risk_breakdown()
        overall = risk_info.get('overall_score') or risk_info.get('overall', {}).get('score') or calculator.calculate_overall_risk()

        # If high risk, create a FraudAttempt record and process it
        if overall and overall >= 60:
            # Create a lightweight fraud attempt for this login check
            fa = FraudAttempt.objects.create(
                user=user,
                attempt_type='login_check',
                description=f'Login-time fraud assessment: score={overall}',
                detected_by='signal:user_logged_in',
                fraud_score=overall,
                confidence_score=risk_info.get('breakdown', {}).get('confidence', 0) if isinstance(risk_info, dict) else 0,
                evidence_data=risk_info
            )

            # Run auto-ban processing for severe cases
            if overall >= 80:
                try:
                    absrv = AutoBanService()
                    absrv.process_fraud_attempt(fa)
                except Exception:
                    pass

    except Exception as e:
        logger.error(f"Error running fraud checks on login for user {getattr(user, 'id', None)}: {e}")


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Log user logout"""
    
    if user and user.is_authenticated:
        log_service.create_log(
            user=user,
            action=AuditLogAction.LOGOUT,
            level=AuditLogLevel.INFO,
            message=f"User {user.email} logged out",
            user_ip=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            request_method=request.method,
            request_path=request.path,
            metadata={
                'session_duration': None,  # Could calculate from login time
                'logout_type': 'manual'  # or 'timeout', 'forced'
            }
        )


@receiver(user_login_failed)
def log_login_failed(sender, credentials, request, **kwargs):
    """Log failed login attempts"""
    
    email = credentials.get('email') or credentials.get('username')
    
    log_service.create_log(
        user=None,
        action=AuditLogAction.LOGIN,
        level=AuditLogLevel.WARNING,
        message=f"Failed login attempt for email/username: {email}",
        user_ip=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        request_method=request.method,
        request_path=request.path,
        success=False,
        error_message="Invalid credentials",
        metadata={
            'attempted_email': email,
            'credentials_keys': list(credentials.keys()),
            'is_brute_force': False  # Would be set by fraud detection
        }
    )


@receiver(post_save, sender=User)
def log_user_changes(sender, instance, created, **kwargs):
    """Log user model changes"""
    
    if created:
        # User registration
        log_service.create_log(
            user=instance,
            action=AuditLogAction.REGISTER,
            level=AuditLogLevel.INFO,
            message=f"New user registered: {instance.email}",
            resource_type='User',
            resource_id=str(instance.id),
            metadata={
                'registration_method': 'web',  # or 'mobile', 'api'
                'referral_code_used': instance.referral_code if hasattr(instance, 'referral_code') else None,
                'signup_source': instance.signup_source if hasattr(instance, 'signup_source') else None
            }
        )
    else:
        # User profile updates
        # Note: To track field changes, we need to compare with old instance
        # This is typically done in pre_save to capture old values
        pass


# ===================== MODEL CHANGE SIGNALS =====================
def register_model_for_audit(model_class, excluded_fields=None):
    """
    Register a model for automatic audit logging
    
    Usage:
        from api.audit_logs.signals import register_model_for_audit
        from api.wallet.models import Wallet
        register_model_for_audit(Wallet)
    """
    
    excluded_fields = excluded_fields or [
        'created_at', 'updated_at', 'last_login',
        'password', 'modified', 'version'
    ]
    
    @receiver(pre_save, sender=model_class)
    def capture_pre_save_state(sender, instance, **kwargs):
        """Capture instance state before save"""
        
        if instance.pk:
            try:
                old_instance = sender.objects.get(pk=instance.pk)
                instance._old_state = {
                    field.name: getattr(old_instance, field.name)
                    for field in sender._meta.fields
                    if field.name not in excluded_fields
                }
            except sender.DoesNotExist:
                instance._old_state = None
        else:
            instance._old_state = None
    
    @receiver(post_save, sender=model_class)
    def log_model_changes(sender, instance, created, **kwargs):
        """Log model create/update"""
        
        # Skip if this is a test or migration
        import sys
        if 'test' in sys.argv or 'migrate' in sys.argv:
            return
        
        # Determine user from request thread
        from django.contrib.auth.models import AnonymousUser
        from django.utils.functional import SimpleLazyObject
        
        user = None
        try:
            from django.contrib.auth import get_user
            from django.core.handlers.wsgi import WSGIRequest
            
            # Try to get user from current request
            for req in [getattr(thread, 'request', None) for thread in threading.enumerate()]:
                if isinstance(req, WSGIRequest):
                    user = req.user
                    if isinstance(user, (AnonymousUser, SimpleLazyObject)):
                        try:
                            user = user._wrapped if hasattr(user, '_wrapped') else user
                        except:
                            user = None
                    break
        except:
            user = None
        
        if created:
            action = 'CREATE'
            message = f"Created {sender.__name__}: {instance}"
            old_data = None
            new_data = {
                field.name: str(getattr(instance, field.name))
                for field in sender._meta.fields
                if field.name not in excluded_fields
            }
        else:
            action = 'UPDATE'
            message = f"Updated {sender.__name__}: {instance}"
            
            old_data = getattr(instance, '_old_state', {})
            new_data = {
                field.name: str(getattr(instance, field.name))
                for field in sender._meta.fields
                if field.name not in excluded_fields
            }
            
            # Clean up
            if hasattr(instance, '_old_state'):
                del instance._old_state
        
        # Only log if there are actual changes
        if not created and old_data == new_data:
            return
        
        # Map to audit action
        action_mapping = {
            'User': AuditLogAction.PROFILE_UPDATE,
            'Wallet': 'WALLET_UPDATE',
            'Transaction': 'TRANSACTION_UPDATE',
            'Offer': 'OFFER_UPDATE',
            'KYC': 'KYC_UPDATE'
        }
        
        audit_action = action_mapping.get(sender.__name__, f"{sender.__name__.upper()}_{action}")
        
        log_service.create_log(
            user=user,
            action=audit_action,
            level=AuditLogLevel.INFO,
            message=message,
            resource_type=sender.__name__,
            resource_id=str(instance.pk),
            old_data=old_data,
            new_data=new_data,
            metadata={
                'model': sender.__name__,
                'action': 'CREATE' if created else 'UPDATE',
                'app_label': sender._meta.app_label,
                'changes': _get_field_changes(old_data, new_data) if not created else None
            }
        )
    
    @receiver(post_delete, sender=model_class)
    def log_model_deletion(sender, instance, **kwargs):
        """Log model deletion"""
        
        log_service.create_log(
            user=None,  # Would need to capture user before deletion
            action=f"{sender.__name__}_DELETE",
            level=AuditLogLevel.WARNING,
            message=f"Deleted {sender.__name__}: {instance}",
            resource_type=sender.__name__,
            resource_id=str(instance.pk),
            old_data={
                field.name: str(getattr(instance, field.name))
                for field in sender._meta.fields
                if field.name not in excluded_fields
            },
            new_data=None,
            metadata={
                'model': sender.__name__,
                'app_label': sender._meta.app_label,
                'deleted_at': timezone.now().isoformat()
            }
        )


def _get_field_changes(old_data, new_data):
    """Extract which fields changed"""
    if not old_data or not new_data:
        return []
    
    changes = []
    for field in set(old_data.keys()) | set(new_data.keys()):
        old_val = old_data.get(field)
        new_val = new_data.get(field)
        
        if old_val != new_val:
            changes.append({
                'field': field,
                'old': str(old_val) if old_val is not None else None,
                'new': str(new_val) if new_val is not None else None
            })
    
    return changes


# ===================== FINANCIAL SIGNALS =====================
def log_transaction_creation(transaction, user=None):
    """Log financial transaction creation"""
    
    log_service.create_log(
        user=user or transaction.user,
        action='TRANSACTION_CREATE',
        level=AuditLogLevel.INFO,
        message=f"Created transaction: {transaction.transaction_type} - {transaction.amount} {transaction.currency}",
        resource_type='Transaction',
        resource_id=str(transaction.id),
        old_data=None,
        new_data={
            'id': str(transaction.id),
            'type': transaction.transaction_type,
            'amount': str(transaction.amount),
            'currency': transaction.currency,
            'status': transaction.status,
            'wallet_id': str(transaction.wallet_id)
        },
        metadata={
            'transaction_type': transaction.transaction_type,
            'gateway': transaction.gateway,
            'reference_id': transaction.reference_id,
            'is_manual': transaction.is_manual if hasattr(transaction, 'is_manual') else False
        }
    )


def log_withdrawal_request(withdrawal, user=None):
    """Log withdrawal request"""
    
    log_service.create_log(
        user=user or withdrawal.user,
        action='WITHDRAWAL_REQUEST',
        level=AuditLogLevel.INFO,
        message=f"Withdrawal request: {withdrawal.amount} {withdrawal.currency} via {withdrawal.withdrawal_method}",
        resource_type='WithdrawalRequest',
        resource_id=str(withdrawal.id),
        metadata={
            'method': withdrawal.withdrawal_method,
            'status': withdrawal.status,
            'fee': str(withdrawal.transaction_fee) if withdrawal.transaction_fee else None,
            'net_amount': str(withdrawal.net_amount) if withdrawal.net_amount else None,
            'payment_details_keys': list(withdrawal.payment_details.keys()) if withdrawal.payment_details else []
        }
    )


# ===================== OFFER SIGNALS =====================
def log_offer_completion(offer_completion, user=None):
    """Log offer completion"""
    
    log_service.create_log(
        user=user or offer_completion.user,
        action=AuditLogAction.OFFER_COMPLETE,
        level=AuditLogLevel.INFO,
        message=f"Offer completed: {offer_completion.offer.title} - Reward: {offer_completion.reward_amount}",
        resource_type='OfferCompletion',
        resource_id=str(offer_completion.id),
        metadata={
            'offer_id': str(offer_completion.offer_id),
            'offer_title': offer_completion.offer.title,
            'reward_amount': str(offer_completion.reward_amount),
            'ad_network': offer_completion.ad_network,
            'is_verified': offer_completion.is_verified,
            'verification_method': offer_completion.verification_method
        }
    )


# ===================== SECURITY SIGNALS =====================
@receiver(request_started)
def log_request_started(sender, environ, **kwargs):
    """Log when a request starts"""
    # Lightweight logging - just track basic info
    pass


@receiver(got_request_exception)
def log_request_exception(sender, request, **kwargs):
    """Log unhandled exceptions"""
    
    exception = kwargs.get('exception')
    
    log_service.create_log(
        user=request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
        action='UNHANDLED_EXCEPTION',
        level=AuditLogLevel.ERROR,
        message=f"Unhandled exception in {request.method} {request.path}: {str(exception)}",
        user_ip=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        request_method=request.method,
        request_path=request.path,
        success=False,
        error_message=str(exception),
        stack_trace=_get_exception_traceback(exception),
        metadata={
            'exception_type': type(exception).__name__,
            'view_name': getattr(request.resolver_match, 'func', None).__name__ if hasattr(request, 'resolver_match') and request.resolver_match else None,
            'view_args': request.resolver_match.args if hasattr(request, 'resolver_match') else None,
            'view_kwargs': request.resolver_match.kwargs if hasattr(request, 'resolver_match') else None
        }
    )


def _get_exception_traceback(exception):
    """Get formatted exception traceback"""
    import traceback
    return ''.join(traceback.format_exception(
        type(exception), exception, exception.__traceback__
    ))


# ===================== KYC SIGNALS =====================
def log_kyc_submission(kyc_document, user=None):
    """Log KYC document submission"""
    
    log_service.create_log(
        user=user or kyc_document.user,
        action=AuditLogAction.KYC_SUBMIT,
        level=AuditLogLevel.INFO,
        message=f"KYC document submitted: {kyc_document.document_type}",
        resource_type='KYCDocument',
        resource_id=str(kyc_document.id),
        metadata={
            'document_type': kyc_document.document_type,
            'status': kyc_document.status,
            'verification_level': kyc_document.verification_level,
            'country': kyc_document.country,
            'is_verified': kyc_document.is_verified,
            'expiry_date': kyc_document.expiry_date.isoformat() if kyc_document.expiry_date else None
        }
    )


def log_kyc_verification(kyc_document, verified_by, status, notes=None):
    """Log KYC verification result"""
    
    action = AuditLogAction.KYC_APPROVE if status == 'APPROVED' else AuditLogAction.KYC_REJECT
    
    log_service.create_log(
        user=verified_by,
        action=action,
        level=AuditLogLevel.INFO,
        message=f"KYC document {status.lower()}: {kyc_document.document_type} for user {kyc_document.user.email}",
        resource_type='KYCDocument',
        resource_id=str(kyc_document.id),
        metadata={
            'document_type': kyc_document.document_type,
            'previous_status': kyc_document._previous_status if hasattr(kyc_document, '_previous_status') else None,
            'new_status': status,
            'verified_by': str(verified_by.id) if verified_by else None,
            'verification_notes': notes,
            'verification_date': timezone.now().isoformat()
        }
    )


# ===================== ADMIN ACTION SIGNALS =====================
def log_admin_action(admin_user, action, target_user=None, details=None):
    """Log admin actions"""
    
    action_mapping = {
        'ban': AuditLogAction.USER_BAN,
        'unban': AuditLogAction.USER_UNBAN,
        'manual_credit': AuditLogAction.MANUAL_CREDIT,
        'manual_debit': AuditLogAction.MANUAL_DEBIT,
        'suspend': 'USER_SUSPEND',
        'activate': 'USER_ACTIVATE'
    }
    
    audit_action = action_mapping.get(action, action.upper())
    
    log_service.create_log(
        user=admin_user,
        action=audit_action,
        level=AuditLogLevel.WARNING if action in ['ban', 'suspend'] else AuditLogLevel.INFO,
        message=f"Admin action: {action} performed by {admin_user.email}" + 
                (f" on user {target_user.email}" if target_user else ""),
        resource_type='User' if target_user else 'System',
        resource_id=str(target_user.id) if target_user else None,
        metadata={
            'admin_user_id': str(admin_user.id),
            'admin_email': admin_user.email,
            'target_user_id': str(target_user.id) if target_user else None,
            'target_email': target_user.email if target_user else None,
            'action': action,
            'details': details or {},
            'timestamp': timezone.now().isoformat()
        }
    )


# ===================== REFERRAL SIGNALS =====================
def log_referral_signup(referrer, referred_user):
    """Log new user signup via referral"""
    
    log_service.create_log(
        user=referrer,
        action=AuditLogAction.REFERRAL_SIGNUP,
        level=AuditLogLevel.INFO,
        message=f"New referral signup: {referred_user.email} referred by {referrer.email}",
        resource_type='User',
        resource_id=str(referred_user.id),
        metadata={
            'referrer_id': str(referrer.id),
            'referrer_email': referrer.email,
            'referred_user_id': str(referred_user.id),
            'referred_email': referred_user.email,
            'referral_code_used': referrer.referral_code if hasattr(referrer, 'referral_code') else None,
            'signup_date': referred_user.date_joined.isoformat() if hasattr(referred_user, 'date_joined') else None
        }
    )


def log_referral_bonus(referrer, referred_user, amount, transaction_id=None):
    """Log referral bonus awarded"""
    
    log_service.create_log(
        user=referrer,
        action=AuditLogAction.REFERRAL_BONUS,
        level=AuditLogLevel.INFO,
        message=f"Referral bonus awarded: {amount} for referring {referred_user.email}",
        resource_type='Transaction',
        resource_id=transaction_id,
        metadata={
            'referrer_id': str(referrer.id),
            'referred_user_id': str(referred_user.id),
            'bonus_amount': str(amount),
            'transaction_id': transaction_id,
            'awarded_at': timezone.now().isoformat()
        }
    )


# ===================== CUSTOM SIGNAL SENDERS =====================
def send_custom_audit_signal(sender, **kwargs):
    """
    Send a custom audit signal from anywhere in the code
    
    Example:
        from api.audit_logs.signals import send_custom_audit_signal
        
        send_custom_audit_signal(
            user=request.user,
            action='CUSTOM_ACTION',
            level='INFO',
            message='Something happened',
            metadata={'key': 'value'}
        )
    """
    
    user = kwargs.get('user')
    action = kwargs.get('action', 'CUSTOM')
    level = kwargs.get('level', AuditLogLevel.INFO)
    message = kwargs.get('message', '')
    metadata = kwargs.get('metadata', {})
    
    log_service.create_log(
        user=user,
        action=action,
        level=level,
        message=message,
        metadata=metadata,
        resource_type=kwargs.get('resource_type'),
        resource_id=kwargs.get('resource_id'),
        old_data=kwargs.get('old_data'),
        new_data=kwargs.get('new_data'),
        success=kwargs.get('success', True),
        error_message=kwargs.get('error_message')
    )


# ===================== INITIALIZATION =====================
def initialize_audit_signals():
    """
    Initialize all audit signals
    
    Call this in apps.py ready() method
    """
    from django.apps import apps
    
    # Register models that should be audited
    models_to_audit = [
        # Add your models here
        # 'api.wallet.models.Wallet',
        # 'api.wallet.models.Transaction',
        # 'api.offerwall.models.Offer',
    ]
    
    for model_path in models_to_audit:
        try:
            app_label, model_name = model_path.split('.')[-2:]
            model = apps.get_model(app_label, model_name)
            register_model_for_audit(model)
            print(f"Registered {model_path} for audit logging")
        except Exception as e:
            print(f"Failed to register {model_path} for audit: {e}")
    
    print("Audit signals initialized")