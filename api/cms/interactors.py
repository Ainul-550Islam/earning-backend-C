# api/cms/interactors.py
"""Service interactors for CMS."""
from django.db import transaction as db_transaction
import logging
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from api.cms.abstracts import BaseService
from api.cms.monitoring import CMSMetrics
from api.cms.caching import CMSCache

logger = logging.getLogger(__name__)
User = get_user_model()


# ── Original Interactors (Preserved) ─────────────────────────────────────

class PostbackProcessingInteractor:
    """
    Full CPAlead postback processing pipeline.
    Coordinates: validation → fraud check → dedup → award → referral → leaderboard → streak → notify.
    """
    def __init__(self):
        self.steps_completed = []
        self.errors = []

    def process(self, params: Dict) -> Dict:
        """Execute full postback pipeline and return comprehensive result."""
        result = {
            'success': False, 'steps': [], 'errors': [],
            'user_id': None, 'coins_awarded': 0, 'lead_id': '',
        }

        # Step 1: Validate params
        from api.cms.validator import validate_cpalead_postback
        valid, errors = validate_cpalead_postback(params)
        if not valid:
            result['errors'] = errors
            return result
        result['steps'].append('validated')

        # Step 2: Resolve user
        from api.cms.selectors import UserSelector
        user = UserSelector.get_by_subid(params.get('subid', ''))
        if not user:
            result['errors'].append(f"User not found: subid={params.get('subid')}")
            return result
        result['user_id'] = user.id
        result['steps'].append('user_resolved')

        # Step 3: Check fraud
        from api.cms.services_new.CPALeadService import FraudDetectionService
        ip = params.get('ip', '')
        fraud, fraud_reason = FraudDetectionService.check(user, ip=ip, subid=params.get('subid', ''))
        if fraud:
            result['errors'].append(f"Fraud detected: {fraud_reason}")
            self._log_fraud(user, ip, fraud_reason, params)
            return result
        result['steps'].append('fraud_checked')

        # Step 4: Dedup check
        lead_id = params.get('lead_id', '')
        from api.cms.repositories import ConversionLogRepository
        if ConversionLogRepository.exists_by_lead_id(lead_id):
            result['success'] = True  # Return success so CPAlead stops retrying
            result['duplicate'] = True
            result['steps'].append('duplicate_detected')
            return result
        result['lead_id'] = lead_id

        # Step 5: Award with atomic transaction
        with db_transaction.atomic():
            payout_usd = Decimal(str(params.get('payout', '0')))
            success, msg, coins = self._award_coins(user, payout_usd, lead_id, params)
            if not success:
                result['errors'].append(msg)
                return result
            result['coins_awarded'] = float(coins)
            result['steps'].append('coins_awarded')

        # Step 6: Post-award side effects (non-critical, don't fail postback)
        self._post_award_effects(user, payout_usd, coins, lead_id)
        result['steps'].extend(['referral_processed', 'leaderboard_updated', 'streak_updated'])
        result['success'] = True
        return result

    def _award_coins(self, user, payout_usd: Decimal, lead_id: str,
                     params: Dict) -> tuple:
        from api.cms.services_new.CPALeadService import VirtualCurrencyService, EarningCapService
        from api.cms.models_new.cpalead import VirtualCurrency, ConversionLog

        vc = VirtualCurrency.get_active()
        if not vc:
            return False, 'No active virtual currency', Decimal('0')

        # Check daily cap
        config = None
        try:
            from api.cms.models_new.extras import CPALeadConfig
            config = CPALeadConfig.get_active()
        except Exception:
            pass

        can_earn, remaining = EarningCapService.can_earn(user, payout_usd, config)
        effective_payout = min(payout_usd, remaining) if not can_earn else payout_usd
        coins = vc.usd_to_virtual(effective_payout)

        # Record conversion
        ConversionLog.objects.create(
            subid=str(user.id),
            lead_id=lead_id,
            payout_usd=effective_payout,
            user=user,
            status='approved',
            campaign_id=params.get('campaign_id', ''),
            virtual_amount_awarded=coins,
            raw_postback_data=params,
        )

        # Award coins
        success = VirtualCurrencyService.award_coins(
            user=user, amount=coins,
            reason=f"CPAlead offer: {lead_id}",
            tx_type='earn_offer', source_id=lead_id,
        )
        if success:
            EarningCapService.record_earning(user, effective_payout, config)
        return success, 'ok', coins

    def _post_award_effects(self, user, payout_usd: Decimal, coins: Decimal, lead_id: str):
        """Non-critical post-award side effects."""
        # Referral bonus
        try:
            from api.cms.services_new.ReferralService import ReferralService
            ReferralService.award_referral_bonus(user, payout_usd, lead_id=lead_id)
        except Exception as e:
            logger.warning(f"[Interactor] Referral bonus failed: {e}")

        # Leaderboard
        try:
            from api.cms.services_new.LeaderboardService import LeaderboardService, StreakService
            LeaderboardService.update_score(user, payout_usd, 'earnings', 'weekly')
            LeaderboardService.update_score(user, Decimal('1'), 'offers', 'weekly')
            StreakService.record_earn(user)
        except Exception as e:
            logger.warning(f"[Interactor] Leaderboard update failed: {e}")

        # User profile totals
        try:
            from api.cms.repositories import UserProfileRepository
            UserProfileRepository.update_earnings(user, usd=payout_usd, coins=coins)
            UserProfileRepository.increment_offer_count(user)
        except Exception as e:
            logger.warning(f"[Interactor] Profile update failed: {e}")

        # Real-time notification
        try:
            from api.cms.services_new.NotificationService import NotificationService
            NotificationService.notify_reward(
                user=user, amount=float(coins), currency='Coins',
                source='CPAlead Offer',
            )
        except Exception as e:
            logger.debug(f"[Interactor] Notification failed: {e}")

        # Hooks (external plugins)
        try:
            from api.cms.hooks import CMSHooks
            CMSHooks.fire('offer_completed', user=user, amount=float(payout_usd), lead_id=lead_id)
        except Exception:
            pass

    def _log_fraud(self, user, ip: str, reason: str, params: Dict):
        try:
            try:
                from api.cms.INTEGRATION_SYSTEM.integ_audit_logs import AuditLogger
            except ImportError:
                pass
            AuditLogger.log(
                action='fraud_detected', source='PostbackInteractor',
                user=user, ip=ip, success=False,
                extra={'reason': reason, 'lead_id': params.get('lead_id', '')},
            )
        except Exception:
            pass


class UserOnboardingInteractor:
    """
    Complete user onboarding flow.
    Steps: create user → setup profile → setup balance → apply referral → welcome notification.
    """
    @db_transaction.atomic
    def onboard(self, username: str, email: str, password: str,
                referral_code: str = '') -> Dict:
        from api.cms.use_cases import RegisterUserUseCase
        uc = RegisterUserUseCase()
        result = uc.execute(username, email, password, referral_code)
        if result['success']:
            # Welcome bonus
            try:
                from django.contrib.auth import get_user_model
                user = get_user_model().objects.get(id=result['user_id'])
                from api.cms.services_new.CPALeadService import VirtualCurrencyService
                from api.cms.constants import DEFAULT_COIN_RATIO
                VirtualCurrencyService.award_coins(
                    user=user,
                    amount=Decimal('50'),  # Welcome bonus: 50 coins
                    reason='Welcome bonus', tx_type='earn_bonus',
                )
            except Exception:
                pass
        return result


class WithdrawalApprovalInteractor:
    """
    Admin approval of withdrawal request.
    Steps: validate request → approve → trigger payment → update user profile → notify.
    """
    def approve(self, admin_user, request_id: int, note: str = '') -> Dict:
        from api.cms.models_new.withdrawal import WithdrawalRequest
        try:
            req = WithdrawalRequest.objects.select_for_update().get(id=request_id, status='pending')
        except WithdrawalRequest.DoesNotExist:
            return {'success': False, 'error': 'Request not found or not pending'}

        with db_transaction.atomic():
            req.approve(admin_user, note)

        # Notify user
        try:
            from api.cms.services_new.NotificationService import NotificationService
            NotificationService.notify_withdrawal(req.user, float(req.net_usd), status='approved')
        except Exception:
            pass

        logger.info(f"[Interactor] Withdrawal #{request_id} approved by {admin_user.username}")
        return {'success': True, 'request_id': request_id, 'status': 'approved'}

    def mark_paid(self, admin_user, request_id: int, transaction_id: str = '') -> Dict:
        from api.cms.models_new.withdrawal import WithdrawalRequest
        try:
            req = WithdrawalRequest.objects.select_for_update().get(
                id=request_id, status__in=['approved', 'processing']
            )
        except WithdrawalRequest.DoesNotExist:
            return {'success': False, 'error': 'Request not found'}

        with db_transaction.atomic():
            req.mark_paid(transaction_id)
            # Update user's withdrawn total
            from api.cms.models_new.withdrawal import UserProfile
            from django.db.models import F
            UserProfile.objects.filter(user=req.user).update(
                total_withdrawn_usd=F('total_withdrawn_usd') + req.net_usd
            )

        try:
            from api.cms.services_new.NotificationService import NotificationService
            NotificationService.notify_withdrawal(req.user, float(req.net_usd), status='paid')
        except Exception:
            pass

        return {'success': True, 'request_id': request_id, 'status': 'paid', 'transaction_id': transaction_id}


# ── Enhanced Interactor Classes ─────────────────────────────────────

class BaseInteractor(BaseService):
    """Base interactor class with common functionality."""
    
    def __init__(self):
        """Initialize interactor."""
        super().__init__()
        self.metrics = CMSMetrics
        self.cache = CMSCache
    
    def validate_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input data."""
        return data
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute interactor."""
        raise NotImplementedError("Subclasses must implement execute method")
    
    def rollback(self, *args, **kwargs) -> bool:
        """Rollback changes if needed."""
        return True


class UserAuthenticationInteractor(BaseInteractor):
    """Handle user authentication and authorization."""
    
    def validate_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate authentication input."""
        required_fields = ['username', 'password']
        
        for field in required_fields:
            if not data.get(field):
                raise ValidationError({field: f"{field} is required"})
        
        return data
    
    def execute(self, auth_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute user authentication."""
        try:
            # Validate input
            validated_data = self.validate_input(auth_data)
            
            username = validated_data['username']
            password = validated_data['password']
            
            # Authenticate user
            from django.contrib.auth import authenticate
            user = authenticate(username=username, password=password)
            
            if not user:
                return {
                    'success': False,
                    'error': 'Invalid credentials',
                    'error_code': 'INVALID_CREDENTIALS'
                }
            
            # Record metrics
            self.metrics.increment('user_login_attempts')
            self.metrics.increment('user_login_success')
            
            # Cache user session data
            cache_key = f"user_session_{user.id}"
            self.cache.set(cache_key, {
                'user_id': user.id,
                'username': user.username,
                'login_time': timezone.now().isoformat()
            }, timeout=3600)
            
            logger.info(f"User authenticated successfully: {username}")
            
            return {
                'success': True,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'is_active': user.is_active
                }
            }
            
        except Exception as e:
            self.metrics.increment('user_login_errors')
            logger.error(f"User authentication failed: {e}")
            return {
                'success': False,
                'error': 'Authentication failed',
                'error_code': 'AUTH_ERROR'
            }


class SurveyInteractionInteractor(BaseInteractor):
    """Handle survey interactions and completions."""
    
    def validate_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate survey interaction input."""
        required_fields = ['survey_id', 'user_id']
        
        for field in required_fields:
            if field not in data:
                raise ValidationError({field: f"{field} is required"})
        
        return data
    
    def execute(self, interaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute survey interaction."""
        try:
            # Validate input
            validated_data = self.validate_input(interaction_data)
            
            user_id = validated_data['user_id']
            survey_id = validated_data['survey_id']
            
            # Get user and survey
            user = User.objects.get(id=user_id)
            from api.cms.models_new.survey import Survey
            survey = Survey.objects.get(id=survey_id)
            
            # Check if survey is active
            if not survey.is_active:
                return {
                    'success': False,
                    'error': 'Survey is not active',
                    'error_code': 'SURVEY_INACTIVE'
                }
            
            # Record metrics
            self.metrics.increment('survey_starts')
            
            logger.info(f"Survey started: user={user.username}, survey={survey.title}")
            
            return {
                'success': True,
                'survey': {
                    'id': survey.id,
                    'title': survey.title,
                    'reward_amount': float(survey.reward_amount),
                    'estimated_time': survey.estimated_time
                }
            }
            
        except Exception as e:
            logger.error(f"Survey interaction failed: {e}")
            return {
                'success': False,
                'error': 'Survey interaction failed',
                'error_code': 'INTERACTION_ERROR'
            }


# ── Interactor Manager ─────────────────────────────────────

class InteractorManager:
    """Manager for accessing all interactors."""
    
    def __init__(self):
        """Initialize interactor manager."""
        self.user_authentication = UserAuthenticationInteractor()
        self.survey_interaction = SurveyInteractionInteractor()
        self.logger = logging.getLogger(f"{__name__}.manager")
    
    def get_interactor(self, interactor_name: str):
        """Get interactor by name."""
        return getattr(self, interactor_name, None)
    
    def execute_interactor(self, interactor_name: str, *args, **kwargs):
        """Execute an interactor by name."""
        interactor = self.get_interactor(interactor_name)
        if not interactor:
            raise ValueError(f"Interactor '{interactor_name}' not found")
        
        try:
            return interactor.execute(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"Interactor execution failed: {interactor_name}, error: {e}")
            raise


# Global enhanced interactor manager
enhanced_interactor_manager = InteractorManager()
