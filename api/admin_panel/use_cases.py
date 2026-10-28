# api/admin_panel/use_cases.py
"""
Admin Panel Use Cases — Clean Architecture business logic layer.
Each use case = one admin action with full validation, execution, side effects.
ViewSets call use cases. Use cases call selectors + repositories + services.
No HTTP here. Fully testable without Django request/response.

"One use case = one admin operation."
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


# ===========================================================================
# RESULT OBJECT
# ===========================================================================

@dataclass
class UseCaseResult:
    success: bool
    data: Any = None
    error: str = ''
    error_code: str = ''
    warnings: List[str] = field(default_factory=list)
    meta: Dict = field(default_factory=dict)

    @classmethod
    def ok(cls, data=None, meta=None, warnings=None) -> 'UseCaseResult':
        return cls(success=True, data=data, meta=meta or {}, warnings=warnings or [])

    @classmethod
    def fail(cls, error: str, error_code: str = '', data=None) -> 'UseCaseResult':
        return cls(success=False, error=error, error_code=error_code, data=data)

    def to_dict(self) -> Dict:
        return {
            'success':    self.success,
            'data':       self.data,
            'error':      self.error,
            'error_code': self.error_code,
            'warnings':   self.warnings,
            'meta':       self.meta,
        }


# ===========================================================================
# USER USE CASES
# ===========================================================================

class BanUserUseCase:
    """
    Ban a user — validates, bans, freezes wallet, cancels payouts, logs, fires events.
    Single responsibility: full user ban lifecycle.
    """

    def execute(
        self,
        user_id: Any,
        reason: str,
        actor,
        freeze_wallet: bool = True,
        cancel_payouts: bool = True,
        send_notification: bool = True,
    ) -> UseCaseResult:
        # 1. Validate
        if not user_id:
            return UseCaseResult.fail('user_id is required', 'MISSING_USER_ID')
        if not reason or len(reason.strip()) < 5:
            return UseCaseResult.fail('reason must be at least 5 characters', 'INVALID_REASON')

        from api.admin_panel.validator import validate_ban_reason
        try:
            reason = validate_ban_reason(reason)
        except Exception as e:
            return UseCaseResult.fail(str(e), 'INVALID_REASON')

        from api.admin_panel.selectors import get_user_by_id
        user = get_user_by_id(user_id)
        if not user:
            return UseCaseResult.fail(f'User {user_id} not found', 'USER_NOT_FOUND')
        if not user.is_active:
            return UseCaseResult.fail(f'User {user_id} is already banned', 'ALREADY_BANNED')
        if user.is_superuser:
            return UseCaseResult.fail('Cannot ban a superuser', 'CANNOT_BAN_SUPERUSER')

        warnings = []
        results = {}

        with transaction.atomic():
            # 2. Ban user
            user.is_active = False
            user.save(update_fields=['is_active'])
            results['user_banned'] = True

            # 3. Freeze wallet
            if freeze_wallet:
                try:
                    from api.wallet.models import Wallet
                    count = Wallet.objects.filter(user_id=user_id, is_locked=False).update(is_locked=True)
                    results['wallets_frozen'] = count
                except Exception as e:
                    warnings.append(f'Wallet freeze failed: {e}')

            # 4. Cancel pending payouts
            if cancel_payouts:
                try:
                    from api.payout_queue.models import PayoutItem
                    count = PayoutItem.objects.filter(user_id=user_id, status='QUEUED').update(status='CANCELLED')
                    results['payouts_cancelled'] = count
                except Exception as e:
                    warnings.append(f'Payout cancel failed: {e}')

            # 5. Revoke active sessions
            try:
                from api.admin_panel.models.activity import AdminSession
                AdminSession.objects.filter(user=user, is_active=True).update(
                    is_active=False, status='force_logout',
                    force_logout_by=actor, ended_at=timezone.now()
                )
            except Exception as e:
                warnings.append(f'Session revoke failed: {e}')

        # 6. Log activity
        try:
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(
                actor=actor, action='ban_user',
                model_name='User', object_id=str(user_id),
                object_repr=user.username,
                changes={'reason': reason, 'freeze_wallet': freeze_wallet, 'results': results},
                status='success',
            )
        except Exception as e:
            warnings.append(f'Activity log failed: {e}')

        # 7. Fire signals
        try:
            from api.admin_panel.signals_cap import fire_user_banned
            fire_user_banned(user_id=user_id, reason=reason, banned_by=actor)
        except Exception as e:
            warnings.append(f'Signal failed: {e}')

        # 8. Send notification
        if send_notification:
            try:
                from api.notifications.models import Notification
                Notification.objects.create(
                    user_id=user_id,
                    title='Account Suspended',
                    message=f'Your account has been suspended. Reason: {reason}',
                    notification_type='account_action',
                )
            except Exception as e:
                warnings.append(f'Notification failed: {e}')

        return UseCaseResult.ok(data=results, warnings=warnings, meta={
            'user': user.username, 'reason': reason
        })


class UnbanUserUseCase:
    def execute(self, user_id: Any, actor, unfreeze_wallet: bool = True) -> UseCaseResult:
        from api.admin_panel.selectors import get_user_by_id
        user = get_user_by_id(user_id)
        if not user:
            return UseCaseResult.fail(f'User {user_id} not found', 'USER_NOT_FOUND')
        if user.is_active:
            return UseCaseResult.fail('User is not banned', 'NOT_BANNED')

        with transaction.atomic():
            user.is_active = True
            user.save(update_fields=['is_active'])
            if unfreeze_wallet:
                try:
                    from api.wallet.models import Wallet
                    Wallet.objects.filter(user_id=user_id, is_locked=True).update(is_locked=False)
                except Exception:
                    pass
        try:
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(actor=actor, action='unban_user', model_name='User',
                              object_id=str(user_id), object_repr=user.username)
        except Exception:
            pass
        try:
            from api.admin_panel.signals_cap import admin_user_unbanned
            admin_user_unbanned.send(sender='admin_panel', user_id=user_id)
        except Exception:
            pass
        return UseCaseResult.ok(data={'user': user.username, 'unbanned': True})


# ===========================================================================
# WITHDRAWAL USE CASES
# ===========================================================================

class ApproveWithdrawalUseCase:
    """Approve a pending withdrawal with full propagation."""

    def execute(
        self,
        item_id: Any,
        actor,
        transaction_ref: str = '',
    ) -> UseCaseResult:
        if not item_id:
            return UseCaseResult.fail('item_id is required', 'MISSING_ITEM_ID')

        try:
            from api.payout_queue.models import PayoutItem
            item = PayoutItem.objects.select_related('user').get(pk=item_id)
        except Exception:
            return UseCaseResult.fail(f'PayoutItem {item_id} not found', 'NOT_FOUND')

        if item.status not in ('QUEUED', 'pending'):
            return UseCaseResult.fail(
                f'Item is {item.status}, not queued for approval', 'INVALID_STATUS'
            )

        # Auto-approve logic check
        from api.admin_panel.logic import should_auto_approve_withdrawal
        from decimal import Decimal
        can_auto, auto_reason = should_auto_approve_withdrawal(
            Decimal(str(item.gross_amount)), item.user_id, item.gateway
        )

        with transaction.atomic():
            item.status = 'approved'
            # PayoutItem uses status change for approval
            if transaction_ref:
                item.gateway_reference = transaction_ref[:200]
            item.save()

        # Log
        try:
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(
                actor=actor, action='approve_withdrawal',
                model_name='PayoutItem', object_id=str(item_id),
                changes={'amount': float(item.gross_amount), 'gateway': item.gateway,
                         'transaction_ref': transaction_ref},
            )
        except Exception:
            pass

        # Fire signals + notifications
        try:
            from api.admin_panel.signals_cap import fire_withdrawal_approved
            fire_withdrawal_approved(item_id, float(item.gross_amount), item.gateway, item.user_id)
        except Exception:
            pass
        try:
            from api.notifications.models import Notification
            Notification.objects.create(
                user_id=item.user_id,
                title='Withdrawal Approved ✅',
                message=f'Your ৳{item.gross_amount} withdrawal via {item.gateway} has been approved.',
                notification_type='withdrawal_approved',
            )
        except Exception:
            pass

        return UseCaseResult.ok(data={
            'item_id': item_id, 'amount': float(item.gross_amount),
            'gateway': item.gateway, 'user': item.user.username,
        })


class RejectWithdrawalUseCase:
    def execute(self, item_id: Any, actor, reason: str) -> UseCaseResult:
        if not reason:
            return UseCaseResult.fail('reason is required', 'MISSING_REASON')
        try:
            from api.payout_queue.models import PayoutItem
            item = PayoutItem.objects.select_related('user').get(pk=item_id)
        except Exception:
            return UseCaseResult.fail(f'PayoutItem {item_id} not found', 'NOT_FOUND')

        if item.status not in ('QUEUED', 'pending'):
            return UseCaseResult.fail(f'Item is {item.status}', 'INVALID_STATUS')

        with transaction.atomic():
            item.status = 'rejected'
            item.rejection_reason = reason
            item.rejected_by = actor
            item.rejected_at = timezone.now()
            item.save()
            # Refund to wallet
            try:
                from api.wallet.models import Wallet, WalletTransaction
                wallet = Wallet.objects.get(user_id=item.user_id)
                wallet.current_balance += item.gross_amount
                wallet.save(update_fields=['balance'])
            except Exception:
                pass

        try:
            from api.notifications.models import Notification
            Notification.objects.create(
                user_id=item.user_id,
                title='Withdrawal Rejected',
                message=f'Your ৳{item.gross_amount} withdrawal was rejected. Reason: {reason}. Amount refunded.',
                notification_type='withdrawal_rejected',
            )
        except Exception:
            pass

        return UseCaseResult.ok(data={'item_id': item_id, 'rejected': True, 'reason': reason})


# ===========================================================================
# FEATURE FLAG USE CASES
# ===========================================================================

class ToggleFeatureFlagUseCase:
    def execute(self, flag_key: str, is_enabled: bool, actor, rollout_pct: int = 100) -> UseCaseResult:
        if not flag_key:
            return UseCaseResult.fail('flag_key is required', 'MISSING_KEY')
        try:
            from api.admin_panel.models.config import FeatureFlag
            flag, created = FeatureFlag.objects.get_or_create(
                flag_key=flag_key,
                defaults={'label': flag_key.replace('_', ' ').title(), 'is_enabled': is_enabled}
            )
            old_val = flag.is_enabled
            flag.is_enabled = is_enabled
            flag.rollout_pct = max(0, min(100, rollout_pct))
            flag.save()
            from django.core.cache import cache
            cache.delete(f'admin_panel:feature_flag:{flag_key}')
            from api.admin_panel.signals_cap import fire_flag_changed
            fire_flag_changed(flag_key, is_enabled, rollout_pct)
            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=actor, action='toggle_feature_flag',
                                  model_name='FeatureFlag', object_repr=flag_key,
                                  changes={'old': old_val, 'new': is_enabled, 'rollout_pct': rollout_pct})
            except Exception: pass
            return UseCaseResult.ok(data={
                'flag_key': flag_key, 'is_enabled': is_enabled,
                'rollout_pct': rollout_pct, 'created': created,
            })
        except Exception as e:
            return UseCaseResult.fail(str(e), 'TOGGLE_FAILED')


# ===========================================================================
# SYSTEM CONFIG USE CASES
# ===========================================================================

class UpdateSystemConfigUseCase:
    def execute(self, key: str, value: Any, actor, group: str = 'general') -> UseCaseResult:
        from api.admin_panel.validator import validate_config_key
        try:
            validate_config_key(key)
        except Exception as e:
            return UseCaseResult.fail(str(e), 'INVALID_KEY')

        try:
            from api.admin_panel.models.config import SystemConfig
            obj, created = SystemConfig.objects.get_or_create(
                key=key, defaults={'group': group}
            )
            if obj.is_readonly and not created:
                return UseCaseResult.fail(f'Config {key} is readonly', 'READONLY')
            old_val = obj.value
            obj.value = str(value)
            obj.group = group
            obj.save()
            from django.core.cache import cache
            cache.delete(f'admin_panel:config:{key}')
            from api.admin_panel.signals_cap import fire_config_changed
            fire_config_changed(key, old_val, str(value), actor)
            return UseCaseResult.ok(data={'key': key, 'value': value, 'created': created})
        except Exception as e:
            return UseCaseResult.fail(str(e), 'UPDATE_FAILED')


# ===========================================================================
# KYC USE CASES
# ===========================================================================

class ApproveKYCUseCase:
    def execute(self, kyc_id: Any, actor, notes: str = '') -> UseCaseResult:
        try:
            from api.kyc.models import KYC
            kyc = KYC.objects.select_related('user').get(pk=kyc_id)
        except Exception:
            return UseCaseResult.fail(f'KYC {kyc_id} not found', 'NOT_FOUND')
        if kyc.status != 'pending':
            return UseCaseResult.fail(f'KYC is {kyc.status}', 'INVALID_STATUS')
        with transaction.atomic():
            kyc.status = 'approved'
            kyc.reviewed_by = actor
            kyc.reviewed_at = timezone.now()
            kyc.reviewer_notes = notes
            kyc.save()
        try:
            from api.notifications.models import Notification
            Notification.objects.create(
                user_id=kyc.user_id, title='Identity Verified ✅',
                message='Your identity verification has been approved.',
                notification_type='kyc_approved',
            )
        except Exception: pass
        return UseCaseResult.ok(data={'kyc_id': kyc_id, 'user': kyc.user.username, 'approved': True})


class RejectKYCUseCase:
    def execute(self, kyc_id: Any, actor, reason: str) -> UseCaseResult:
        if not reason:
            return UseCaseResult.fail('reason is required', 'MISSING_REASON')
        try:
            from api.kyc.models import KYC
            kyc = KYC.objects.select_related('user').get(pk=kyc_id)
        except Exception:
            return UseCaseResult.fail(f'KYC {kyc_id} not found', 'NOT_FOUND')
        if kyc.status != 'pending':
            return UseCaseResult.fail(f'KYC is {kyc.status}', 'INVALID_STATUS')
        with transaction.atomic():
            kyc.status = 'rejected'
            kyc.reviewed_by = actor
            kyc.reviewed_at = timezone.now()
            kyc.rejection_reason = reason
            kyc.save()
        try:
            from api.notifications.models import Notification
            Notification.objects.create(
                user_id=kyc.user_id, title='Identity Verification Rejected',
                message=f'KYC rejected. Reason: {reason}. Please resubmit.',
                notification_type='kyc_rejected',
            )
        except Exception: pass
        return UseCaseResult.ok(data={'kyc_id': kyc_id, 'rejected': True, 'reason': reason})


# ===========================================================================
# MAINTENANCE USE CASES
# ===========================================================================

class EnableMaintenanceUseCase:
    def execute(self, message: str, duration_minutes: int, actor) -> UseCaseResult:
        if not message:
            return UseCaseResult.fail('message is required', 'MISSING_MESSAGE')
        try:
            from api.admin_panel.services.MaintenanceModeService import MaintenanceModeService
            MaintenanceModeService.enable(message=message, duration_minutes=duration_minutes)
            from api.admin_panel.signals_cap import admin_maintenance_on
            admin_maintenance_on.send(sender='admin_panel', message=message, duration_minutes=duration_minutes)
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(actor=actor, action='enable_maintenance',
                              changes={'message': message, 'duration': duration_minutes})
            return UseCaseResult.ok(data={'message': message, 'duration_minutes': duration_minutes})
        except Exception as e:
            return UseCaseResult.fail(str(e), 'MAINTENANCE_FAILED')


# ===========================================================================
# BULK USE CASES
# ===========================================================================

class BulkBanUsersUseCase:
    """Bulk ban up to 5000 users via Celery task."""

    def execute(self, user_ids: List[Any], reason: str, actor) -> UseCaseResult:
        from api.admin_panel.validator import validate_user_ids
        try:
            validated_ids = validate_user_ids(user_ids, max_count=5000)
        except Exception as e:
            return UseCaseResult.fail(str(e), 'INVALID_IDS')
        if not reason or len(reason) < 5:
            return UseCaseResult.fail('Reason must be at least 5 chars', 'INVALID_REASON')
        try:
            from api.admin_panel.tasks_cap import task_bulk_ban_users
            task_bulk_ban_users.delay(validated_ids, reason, actor.pk)
            return UseCaseResult.ok(data={'queued': len(validated_ids), 'reason': reason})
        except Exception as e:
            return UseCaseResult.fail(str(e), 'QUEUE_FAILED')


class BulkApproveWithdrawalsUseCase:
    def execute(self, item_ids: List[Any], actor) -> UseCaseResult:
        if not item_ids:
            return UseCaseResult.fail('item_ids required', 'MISSING_IDS')
        approved = errors = 0
        use_case = ApproveWithdrawalUseCase()
        for item_id in item_ids[:500]:
            result = use_case.execute(item_id, actor)
            if result.success:
                approved += 1
            else:
                errors += 1
        return UseCaseResult.ok(data={'approved': approved, 'errors': errors, 'total': len(item_ids)})


# ===========================================================================
# WALLET ADJUSTMENT USE CASE
# ===========================================================================

class AdjustWalletUseCase:
    def execute(self, user_id: Any, amount: float, reason: str, actor) -> UseCaseResult:
        if not reason:
            return UseCaseResult.fail('reason required', 'MISSING_REASON')
        if amount == 0:
            return UseCaseResult.fail('amount cannot be zero', 'ZERO_AMOUNT')
        try:
            from api.wallet.models import Wallet
            wallet = Wallet.objects.get(user_id=user_id)
            old_balance = float(wallet.current_balance)
            from decimal import Decimal
            wallet.current_balance += Decimal(str(amount))
            if wallet.current_balance < 0:
                return UseCaseResult.fail('Balance cannot go negative', 'NEGATIVE_BALANCE')
            wallet.save(update_fields=['balance'])
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(
                actor=actor, action='adjust_wallet',
                model_name='Wallet', object_id=str(wallet.pk),
                changes={'user_id': user_id, 'amount': amount, 'reason': reason,
                         'old_balance': old_balance, 'new_balance': float(wallet.current_balance)},
            )
            return UseCaseResult.ok(data={
                'user_id': user_id, 'amount': amount,
                'old_balance': old_balance, 'new_balance': float(wallet.current_balance),
            })
        except Exception as e:
            return UseCaseResult.fail(str(e), 'ADJUST_FAILED')


# ===========================================================================
# USE CASE REGISTRY
# ===========================================================================

USE_CASES = {
    'ban_user':               BanUserUseCase,
    'unban_user':             UnbanUserUseCase,
    'approve_withdrawal':     ApproveWithdrawalUseCase,
    'reject_withdrawal':      RejectWithdrawalUseCase,
    'toggle_feature_flag':    ToggleFeatureFlagUseCase,
    'update_system_config':   UpdateSystemConfigUseCase,
    'approve_kyc':            ApproveKYCUseCase,
    'reject_kyc':             RejectKYCUseCase,
    'enable_maintenance':     EnableMaintenanceUseCase,
    'bulk_ban_users':         BulkBanUsersUseCase,
    'bulk_approve_withdrawals': BulkApproveWithdrawalsUseCase,
    'adjust_wallet':          AdjustWalletUseCase,
}


def execute_use_case(name: str, **kwargs) -> UseCaseResult:
    """Execute a use case by name."""
    cls = USE_CASES.get(name)
    if not cls:
        return UseCaseResult.fail(f"Unknown use case: {name}", 'UNKNOWN_USE_CASE')
    return cls().execute(**kwargs)