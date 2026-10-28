# api/cms/use_cases.py
"""Business use cases for CMS."""
from django.db import transaction as db_transaction
from typing import Tuple
import logging
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.exceptions import ValidationError

from api.cms.abstracts import BaseService
from api.cms.monitoring import CMSMetrics
from api.cms.caching import CMSCache

logger = logging.getLogger(__name__)
User = get_user_model()


# ── Original Use Cases (Preserved) ─────────────────────────────────────

class ProcessCPALeadPostbackUseCase:
    """
    Process a CPAlead postback notification.
    Steps: validate → dedup → resolve user → check fraud → award coins → referral bonus → notify.
    """
    def execute(self, params: Dict) -> Tuple[bool, str]:
        from api.cms.services_new.CPALeadService import CPALeadService
        return CPALeadService.handle_postback(params)


class UnlockContentUseCase:
    """
    Unlock content locker after successful CPAlead offer completion.
    Steps: verify lead_id → check locker → create unlock record → return content.
    """
    def execute(self, locker_id: int, lead_id: str,
                user=None, session_key: str = '') -> Dict:
        from api.cms.repositories import ConversionLogRepository, NotificationRepository
        from api.cms.selectors import LockerSelector

        locker = LockerSelector.get_locker(locker_id)
        if not locker:
            return {'success': False, 'error': 'Locker not found'}

        # Verify the lead_id belongs to a valid conversion
        if lead_id and not ConversionLogRepository.exists_by_lead_id(lead_id):
            return {'success': False, 'error': 'Invalid lead_id — complete an offer first'}

        # Check if already unlocked
        if LockerSelector.is_unlocked_for_user(locker_id, user, session_key):
            return {
                'success': True, 'already_unlocked': True,
                'content': locker.locked_content,
            }

        # Create unlock record
        try:
            from api.cms.models_new.cpalead import LockerUnlock
            from django.utils import timezone
            import datetime
            expires_at = None
            if locker.unlock_mode == '24h':
                expires_at = timezone.now() + datetime.timedelta(hours=24)
            elif locker.unlock_mode == '7d':
                expires_at = timezone.now() + datetime.timedelta(days=7)

            LockerUnlock.objects.create(
                locker=locker, user=user,
                session_key=session_key or '',
                lead_id=lead_id, is_valid=True,
                expires_at=expires_at,
            )
            # Update locker stats
            from django.db.models import F
            type(locker).objects.filter(pk=locker_id).update(
                total_unlocks=F('total_unlocks') + 1
            )
            # Notify user
            if user and user.is_authenticated:
                NotificationRepository.create(
                    user=user, notification_type='offer',
                    title='Content Unlocked!',
                    message=f'You unlocked: {locker.name}',
                )
        except Exception as e:
            logger.error(f"[UseCase] Unlock create failed: {e}")

        return {
            'success': True, 'already_unlocked': False,
            'content': locker.locked_content,
            'locker_name': locker.name,
        }


class RequestWithdrawalUseCase:
    """
    Process a withdrawal request.
    Steps: validate amount → check balance → check minimum → deduct coins → create request → notify.
    """
    def execute(self, user, method: str, account_id: str,
                coins_amount: Decimal) -> Dict:
        from api.cms.services_new.WithdrawalService import WithdrawalService
        return WithdrawalService.request_withdrawal(user, method, account_id, coins_amount)


class ApplyReferralCodeUseCase:
    """
    Apply referral code for new user.
    Steps: validate code → check not self-referral → check not already referred → create relationship.
    """
    def execute(self, user, code: str) -> Dict:
        from api.cms.services_new.ReferralService import ReferralService
        return ReferralService.apply_referral(user, code)


class CompleteQuizUseCase:
    """
    Complete a quiz attempt.
    Steps: validate answers → calculate result → award coins → update stats → notify.
    """
    def execute(self, attempt_id: int, answers: Dict) -> Dict:
        from api.cms.services_new.QuizService import QuizService
        return QuizService.submit_answers(attempt_id, answers)


class PublishContentUseCase:
    """
    Publish a CMS page or blog post.
    Steps: check workflow state → check approvals → set status=published → invalidate cache → notify.
    """
    def execute(self, content_obj, by_user) -> Dict:
        from api.cms.services_new.WorkflowService import WorkflowService
        result = WorkflowService.publish(content_obj, by_user)
        if result['success']:
            # Invalidate search index
            from api.cms.search import CMSSearchEngine
            CMSSearchEngine.index_content(
                type(content_obj).__name__.lower(), content_obj.pk
            )
        return result


class SubmitFormUseCase:
    """
    Submit a dynamic form.
    Steps: validate fields → check submission limits → sanitize → save → send notifications → award reward.
    """
    def execute(self, form_id: int, data: Dict, user=None,
                session_key: str = '', ip: str = '') -> Dict:
        from api.cms.services_new.FormBuilderService import FormBuilderService
        return FormBuilderService.submit_form(form_id, data, user, session_key, ip)


class CreateVideoContentUseCase:
    """
    Create AI-generated video content.
    Steps: validate topic → check AI credits → generate script → save → link smartlink.
    """
    def execute(self, topic: str, platform: str = 'youtube_shorts',
                style: str = 'story', user=None,
                smartlink_id: int = None) -> Dict:
        from api.cms.services_new.VideoContentService import VideoContentService
        return VideoContentService.create_video(
            topic=topic, platform=platform, style=style,
            user=user, smartlink_id=smartlink_id, use_ai=True,
        )


class RegisterUserUseCase:
    """
    Register a new user with CMS setup.
    Steps: create user → create profile → create virtual balance → create referral code → apply referral code if provided.
    """
    @db_transaction.atomic
    def execute(self, username: str, email: str, password: str,
                referral_code: str = '') -> Dict:
        from django.contrib.auth import get_user_model
        User = get_user_model()

        if User.objects.filter(username=username).exists():
            return {'success': False, 'error': 'Username already taken'}
        if User.objects.filter(email=email).exists():
            return {'success': False, 'error': 'Email already registered'}

        user = User.objects.create_user(
            username=username, email=email, password=password
        )

        # Receivers auto-create profile, balance, referral code
        # Apply referral code if provided
        if referral_code:
            from api.cms.services_new.ReferralService import ReferralService
            ReferralService.apply_referral(user, referral_code)

        logger.info(f"[UseCase] New user registered: {username}")
        return {
            'success': True,
            'user_id': user.id,
            'username': user.username,
        }


class AwardManualBonusUseCase:
    """
    Admin: manually award coins to a user.
    Steps: validate amount → award coins → log audit → notify user.
    """
    def execute(self, admin_user, target_user, coins: Decimal,
                reason: str = 'Manual bonus') -> Dict:
        if coins <= 0:
            return {'success': False, 'error': 'Amount must be positive'}
        try:
            from api.cms.services_new.CPALeadService import VirtualCurrencyService
            success = VirtualCurrencyService.award_coins(
                user=target_user, amount=coins,
                reason=reason, tx_type='earn_bonus',
            )
            if success:
                try:
                    from api.cms.INTEGRATION_SYSTEM.integ_audit_logs import AuditLogger
                except ImportError:
                    pass
                AuditLogger.log(
                    action='manual_bonus_award',
                    source='AdminUseCase',
                    user=admin_user,
                    success=True,
                    extra={'target_user': target_user.id, 'coins': float(coins), 'reason': reason},
                )
            return {'success': success, 'coins_awarded': float(coins)}
        except Exception as e:
            logger.error(f"[UseCase] Manual bonus failed: {e}")
            return {'success': False, 'error': str(e)}


class SuspendUserUseCase:
    """
    Admin: suspend a user account.
    Steps: update profile → freeze earnings → log audit → notify user.
    """
    def execute(self, admin_user, target_user, reason: str = '') -> Dict:
        try:
            from api.cms.models_new.withdrawal import UserProfile
            from django.utils import timezone
            UserProfile.objects.filter(user=target_user).update(
                is_suspended=True,
                suspension_reason=reason,
                earning_frozen_until=timezone.now() + __import__('datetime').timedelta(days=365),
            )
            try:
                from api.cms.INTEGRATION_SYSTEM.integ_audit_logs import AuditLogger
            except ImportError:
                pass
            AuditLogger.log(
                action='user_suspended', source='AdminUseCase',
                user=admin_user, success=True,
                extra={'target_user': target_user.id, 'reason': reason},
            )
            return {'success': True, 'user': target_user.username, 'reason': reason}
        except Exception as e:
            return {'success': False, 'error': str(e)}


# ── Enhanced Use Cases ─────────────────────────────────────

class BaseUseCase(BaseService):
    """Base use case class with common functionality."""
    
    def __init__(self):
        """Initialize use case."""
        super().__init__()
        self.metrics = CMSMetrics
        self.cache = CMSCache
    
    def validate_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input data."""
        return data
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute use case."""
        raise NotImplementedError("Subclasses must implement execute method")


class EnhancedUserRegistrationUseCase(BaseUseCase):
    """Handle user registration with validation and profile creation."""
    
    def __init__(self):
        super().__init__()
        self.required_fields = ['username', 'email', 'password']
    
    def validate_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate registration input."""
        errors = {}
        
        for field in self.required_fields:
            if not data.get(field):
                errors[field] = f"{field} is required"
        
        if errors:
            raise ValidationError(errors)
        
        return data
    
    def execute(self, user_data: Dict[str, Any]) -> User:
        """Execute user registration."""
        try:
            with transaction.atomic():
                validated_data = self.validate_input(user_data)
                
                user = User.objects.create_user(
                    username=validated_data['username'],
                    email=validated_data['email'],
                    password=validated_data['password']
                )
                
                self.metrics.record_user_registration()
                
                cache_key = f"user_profile_{user.id}"
                self.cache.set(cache_key, {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'created_at': user.created_at.isoformat()
                }, timeout=3600)
                
                logger.info(f"User registered successfully: {user.username}")
                return user
                
        except Exception as e:
            logger.error(f"User registration failed: {e}")
            raise


# ── Use Case Manager ─────────────────────────────────────

class UseCaseManager:
    """Manager for accessing all use cases."""
    
    def __init__(self):
        """Initialize use case manager."""
        self.enhanced_user_registration = EnhancedUserRegistrationUseCase()
        self.logger = logging.getLogger(f"{__name__}.manager")
    
    def get_use_case(self, use_case_name: str):
        """Get use case by name."""
        return getattr(self, use_case_name, None)
    
    def execute_use_case(self, use_case_name: str, *args, **kwargs):
        """Execute a use case by name."""
        use_case = self.get_use_case(use_case_name)
        if not use_case:
            raise ValueError(f"Use case '{use_case_name}' not found")
        
        try:
            return use_case.execute(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"Use case execution failed: {use_case_name}, error: {e}")
            raise


# Global enhanced use case manager
enhanced_use_case_manager = UseCaseManager()
