# api/referral/INTEGRATION_SYSTEM/data_bridge.py
# Data bridge — transforms data between referral module and other modules
# Normalizes different data formats across api/tasks, api/offer_inventory, etc.
# ============================================================

import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Union
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class DataBridge:
    """
    Transforms and normalizes data between referral and other modules.
    Each module has different model structures — this handles the mapping.
    """

    # ── User Resolution ───────────────────────────────────────────────────────

    @staticmethod
    def resolve_user(user_or_id: Union[Any, int]) -> Optional[Any]:
        """
        Resolve a user from ID, object, or username.
        Works across all module patterns.
        """
        if user_or_id is None:
            return None

        # Already a user object
        if hasattr(user_or_id, 'pk') and hasattr(user_or_id, 'username'):
            return user_or_id

        # Integer ID
        try:
            user_id = int(user_or_id)
            return User.objects.select_related().get(id=user_id)
        except (ValueError, TypeError, User.DoesNotExist):
            pass

        # String username
        if isinstance(user_or_id, str):
            try:
                return User.objects.get(username=user_or_id)
            except User.DoesNotExist:
                pass

        return None

    # ── Amount Normalization ──────────────────────────────────────────────────

    @staticmethod
    def to_decimal(value: Any) -> Decimal:
        """
        Safely convert any value to Decimal for commission calculations.
        Handles: float, int, str, Decimal, None.
        """
        if value is None:
            return Decimal('0')
        try:
            return Decimal(str(value)).quantize(Decimal('0.0001'))
        except (InvalidOperation, TypeError, ValueError):
            logger.warning(f'[DataBridge] Cannot convert to Decimal: {value!r}')
            return Decimal('0')

    @staticmethod
    def safe_amount(value: Any, min_val: float = 0) -> Decimal:
        """Convert and validate amount — must be above min_val."""
        amount = DataBridge.to_decimal(value)
        if amount <= Decimal(str(min_val)):
            return Decimal('0')
        return amount

    # ── Task Completion Normalization ─────────────────────────────────────────

    @staticmethod
    def from_task_completion(completion) -> Dict:
        """
        Normalize api/tasks UserTaskCompletion to referral format.
        Handles different task model structures.
        """
        if completion is None:
            return {}

        # Try different field names for earned amount
        amount = (
            getattr(completion, 'coins_earned', None)
            or getattr(completion, 'reward_amount', None)
            or getattr(completion, 'earned_amount', None)
            or getattr(completion, 'amount', None)
            or 0
        )

        task = getattr(completion, 'task', None)
        user = getattr(completion, 'user', None)

        return {
            'user': user,
            'task': task,
            'task_id': str(task.id) if task else str(getattr(completion, 'task_id', '')),
            'earned_amount': DataBridge.to_decimal(amount),
            'source_type': 'task',
            'completion_id': str(completion.id) if hasattr(completion, 'id') else '',
        }

    # ── Conversion/Offer Normalization ────────────────────────────────────────

    @staticmethod
    def from_offer_conversion(conversion) -> Dict:
        """
        Normalize api/offer_inventory Conversion to referral format.
        Handles UserTaskCompletion and postback_engine Conversion.
        """
        if conversion is None:
            return {}

        # User net reward after platform fee
        user_reward = (
            getattr(conversion, 'user_net_reward', None)
            or getattr(conversion, 'payout', None)
            or getattr(conversion, 'user_payout', None)
            or getattr(conversion, 'reward', None)
            or 0
        )

        offer = getattr(conversion, 'offer', None)
        user = getattr(conversion, 'user', None)

        return {
            'user': user,
            'conversion': conversion,
            'offer_id': str(
                offer.id if offer else getattr(conversion, 'offer_id', '')
            ),
            'user_net_reward': DataBridge.to_decimal(user_reward),
            'source_type': 'offer',
            'conversion_id': str(conversion.id) if hasattr(conversion, 'id') else '',
        }

    # ── Wallet Normalization ──────────────────────────────────────────────────

    @staticmethod
    def from_wallet_withdrawal(withdrawal) -> Dict:
        """Normalize api/wallet Withdrawal to referral format."""
        if withdrawal is None:
            return {}

        user = None
        if hasattr(withdrawal, 'wallet') and withdrawal.wallet:
            user = getattr(withdrawal.wallet, 'user', None)
        if not user:
            user = getattr(withdrawal, 'user', None)

        amount = (
            getattr(withdrawal, 'amount', None)
            or getattr(withdrawal, 'net_amount', None)
            or 0
        )

        return {
            'user': user,
            'amount': DataBridge.to_decimal(amount),
            'transaction_id': str(withdrawal.id) if hasattr(withdrawal, 'id') else '',
            'source_type': 'withdrawal',
        }

    # ── Referral Settings to Dict ─────────────────────────────────────────────

    @staticmethod
    def settings_to_dict(settings_obj) -> Dict:
        """Serialize ReferralSettings for API responses."""
        if not settings_obj:
            return {
                'level1_rate': 10, 'level2_rate': 5, 'level3_rate': 2,
                'is_active': False, 'commission_hold_days': 7,
            }
        return {
            'level1_rate': float(settings_obj.level1_commission_rate),
            'level2_rate': float(settings_obj.level2_commission_rate),
            'level3_rate': float(settings_obj.level3_commission_rate),
            'direct_signup_bonus': float(settings_obj.direct_signup_bonus),
            'referrer_signup_bonus': float(settings_obj.referrer_signup_bonus),
            'commission_hold_days': settings_obj.commission_hold_days,
            'is_active': settings_obj.is_active,
            'max_depth': settings_obj.max_referral_depth,
        }

    # ── Commission Result Formatting ──────────────────────────────────────────

    @staticmethod
    def format_commission_results(results: list) -> list:
        """Format commission results for API responses."""
        formatted = []
        for r in results:
            formatted.append({
                'beneficiary': r.get('beneficiary', ''),
                'level': r.get('level', 1),
                'commission_amount': float(r.get('commission', 0)),
                'commission_rate': float(r.get('rate', 0)),
                'held': r.get('held', False),
            })
        return formatted

    # ── Referral Summary for Other Modules ───────────────────────────────────

    @staticmethod
    def get_referral_summary_for_user_profile(user) -> Dict:
        """
        Used by api/users profile views.
        Returns referral data in format expected by user profile.
        """
        try:
            from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge
            bridge = get_bridge()
            stats = bridge.get_user_referral_summary(user)

            return {
                'referral_code': stats.get('referral_code', ''),
                'referral_link': f"/ref/{stats.get('referral_code', '')}",
                'total_referrals': stats.get('total_referrals', 0),
                'active_referrals': stats.get('active_referrals', 0),
                'total_commission': stats.get('total_commission', 0),
                'this_month_commission': stats.get('this_month_commission', 0),
                'level1': {
                    'count': stats.get('level1_count', 0),
                    'commission': stats.get('level1_commission', 0),
                },
                'level2': {
                    'count': stats.get('level2_count', 0),
                    'commission': stats.get('level2_commission', 0),
                },
                'level3': {
                    'count': stats.get('level3_count', 0),
                    'commission': stats.get('level3_commission', 0),
                },
            }
        except Exception as e:
            logger.warning(f'[DataBridge] get_referral_summary_for_user_profile: {e}')
            return {
                'referral_code': getattr(user, 'referral_code', ''),
                'referral_link': '',
                'total_referrals': 0,
                'total_commission': 0,
            }

    # ── Promotions Module Compatibility ───────────────────────────────────────

    @staticmethod
    def promotions_referral_manager_compat(user_id: int, earning_amount: Decimal) -> list:
        """
        Compatibility layer for api/promotions/referral/referral_manager.py
        That module uses cache-based referral tree (data loss risk!).
        This bridges it to the proper database-backed system.
        """
        try:
            from django.contrib.auth import get_user_model
            from api.referral.services.ReferralService import ReferralService
            UserModel = get_user_model()
            user = UserModel.objects.get(id=user_id)
            results = ReferralService.process_multilevel_commission(
                earner=user,
                earned_amount=DataBridge.to_decimal(earning_amount),
                source_type='promotion',
            )
            # Return in promotions format
            return [
                {
                    'level': r['level'],
                    'referrer': r['beneficiary'],
                    'commission': str(r['commission']),
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f'[DataBridge] promotions_compat error: {e}')
            return []